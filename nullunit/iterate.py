import json
import os
import glob
import shutil
import logging
import socket
import re
import time
from datetime import datetime
from nullunit.common import getPackrat
from nullunit.confluence import uploadToConfluence

from procutils import execute, execute_lines_rc

GIT_CMD = '/usr/bin/git'
MAKE_CMD = '/usr/bin/make'
WORK_DIR = '/nullunit/src'  # if the dir is a ends in src, it will make go and it's GOPATH happy

SCORE_RE = re.compile( '^==-- SCORE: ([0-9])? --==$' )

# make sure something like "make: *** No rule to make target `XXXX', needed by `XXXX'.  Stop." still fails
DIDNOTHING_RE_LIST = [ re.compile( '^make(\[[0-9]+\])?: \*\*\* No rule to make .* Stop\.$' ), re.compile( '^make(\[[0-9]+\])?: Nothing to be done for .*\.$' ) ]

if os.path.exists( '/usr/bin/apt-get' ):
  PKG_UPDATE = '/usr/bin/apt-get update'
  PKG_INSTALL = '/usr/bin/apt-get install -y %s'

elif os.path.exists( '/usr/bin/yum' ):
  PKG_UPDATE = '/usr/bin/yum clean all'
  PKG_INSTALL = '/usr/bin/yum install -y %s'

else:
  raise Exception( 'can\'t detect package manager' )

def _makeDidNothing( results ):
  if len( results ) != 1:
    return False

  for item in DIDNOTHING_RE_LIST:
    if item.search( results[0] ):
      return True

  return False


def _makeAndGetValues( mcp, state, target, args, env ):
  ( item_list, rc ) = execute_lines_rc( '%s -s %s %s' % ( MAKE_CMD, target, ' '.join( args ) ), state[ 'dir' ], env=env )

  if rc != 0:
    if rc == 2 and _makeDidNothing( item_list ):
      return []

    else:
      logging.info( 'iterate: error getting requires' )
      mcp.setResults( 'Error getting requires:\n' + '\n'.join( item_list ) )
      return None

  results = []
  for item in item_list:
    if item.startswith( 'make:' ) or item.startswith( 'make[' ): # make was unhappy about something, skip that line.... if it was important it will come out later
      continue

    item = item.strip()
    if item:
      results.append( item  )

  return results


def _isPackageBuild( state ):
  return state[ 'target' ] in ( 'dpkg', 'rpm', 'respkg', 'resource' )


def _isPackageLintTestBuild( state ):
  return state[ 'target' ] in ( 'test', 'lint', 'dpkg', 'rpm', 'respkg', 'resource', 'docs' )

def readState( file ):
  try:
    state = json.loads( open( file, 'r' ).read() )
  except:
    return None

  return state


def writeState( file, state ):
  open( file, 'w' ).write( json.dumps( state ) )


def doStep( state, mcp, config ):
  start_state = state[ 'state' ]
  mcp.sendStatus( 'Executing Stage "%s"' % start_state )
  logging.info( 'iterate: Executing Stage "%s"' % start_state )

  if start_state == 'clone':
    state[ 'dir' ] = doClone( state )
    state[ 'state' ] = 'checkout'

  elif start_state == 'checkout':
    doCheckout( state )
    state[ 'state' ] = 'requires'

  elif start_state == 'requires':
    if doRequires( state, mcp, config ):
      state[ 'state' ] = 'target'

    else:
      state[ 'state' ] = 'failed'
      mcp.setSuccess( False )

  elif start_state == 'target':
    if doTarget( state, mcp, config ):
      state[ 'state' ] = 'done'
      mcp.setSuccess( True )

    else:
      state[ 'state' ] = 'failed'
      mcp.setSuccess( False )

  mcp.sendStatus( 'Stage "%s" Complete' % start_state )
  logging.info( 'iterate: Stage "%s" Complete' % start_state )


def doClone( state ):
  try:
    os.makedirs( WORK_DIR )

  except OSError as e:
    if e.errno == 17: # allready exists
      shutil.rmtree( WORK_DIR )
      os.makedirs( WORK_DIR )

    else:
      raise e

  logging.info( 'iterate: cloning "%s"' % state[ 'url' ] )
  execute( '%s clone %s' % ( GIT_CMD, state[ 'url' ] ), WORK_DIR )
  return glob.glob( '%s/*' % WORK_DIR )[0]


def doCheckout( state ):
  logging.info( 'iterate: checking out "%s"' % state[ 'branch' ] )
  execute( '%s checkout %s' % ( GIT_CMD, state[ 'branch' ] ), state[ 'dir' ] )

  tmp = int( time.time() ) - ( 3600 * 24 )  # hopfully nothing is clock skewed more than this
  times = ( tmp, tmp )

  for ( root, dirname_list, filename_list ) in os.walk( state[ 'dir' ] ):  # go through and `touch` everything.
    for filename in filename_list:
      try:                                                                   # clock skew is a fact of life, we are building everything anyway
        os.utime( os.path.join( root, filename ), times )                    # this helps make not complain about the future
      except OSError:
        pass


def doRequires( state, mcp, config ):
  logging.info( 'iterate: getting requires for "%s"' % state[ 'target' ] )
  args = []
  args.append( 'NULLUNIT=1' )

  env = os.environ
  env[ 'DEBIAN_PRIORITY' ] = 'critical'
  env[ 'DEBIAN_FRONTEND' ] = 'noninteractive'

  if not _isPackageLintTestBuild( state ):
    values = {}
    args.append( 'RESOURCE_NAME="%s"' % config.get( 'mcp', 'resource_name' ) )
    args.append( 'RESOURCE_INDEX=%s' % config.get( 'mcp', 'resource_index' ) )
    item_list = _makeAndGetValues( mcp, state, '%s-config' % state[ 'target' ], args, env )
    if item_list is None:
      return False

    for item in item_list:
      ( key, value ) = item.split( ':', 1 )
      if len( value ) > 1 and value[0] in ( '[', '{' ):
        value = json.loads( value )

      values[ key ] = value

    if values:
      if not mcp.setConfigValues( values, config.get( 'mcp', 'resource_name' ), config.get( 'mcp', 'resource_index' ), 1 ):
        raise Exception( 'iterate: Error Setting Configuration Vaules' )

  required_list = _makeAndGetValues( mcp, state, '%s-requires' % state[ 'target' ], args, env )
  if required_list is None:
    return False

  logging.info( 'iterate: updating pkg metadata' )
  execute( PKG_UPDATE )

  for required in required_list:
    logging.info( 'iterate: installing "%s"' % required )
    execute( PKG_INSTALL % required )

  return True


def doTarget( state, mcp, config ): # we allways setResults and setScore to clear out any previous run's results there might be
  args = []
  args.append( 'NULLUNIT=1' )

  if _isPackageBuild( state ):
    packrat = getPackrat( config )
    if not packrat:
      raise Exception( 'iterate: Error Connecting to packrat' )

    logging.info( 'iterate: executing clean' )
    ( results, rc ) = execute_lines_rc( '%s clean' % MAKE_CMD, state[ 'dir' ] )
    if rc != 0:
      if rc == 2 and not _makeDidNothing( results ):
        mcp.setResults( 'Error with clean\n' + '\n'.join( results ) )
        return False

  if not _isPackageLintTestBuild( state ):
    args.append( 'RESOURCE_NAME="%s"' % config.get( 'mcp', 'resource_name' ) )
    args.append( 'RESOURCE_INDEX=%s' % config.get( 'mcp', 'resource_index' ) )

  logging.info( 'iterate: executing setup "%s"' % state[ 'target' ] )
  ( results, rc ) = execute_lines_rc( '%s %s-setup %s' % ( MAKE_CMD, state[ 'target' ], ' '.join( args ) ), state[ 'dir' ] )
  if rc != 0:
    if rc == 2 and not _makeDidNothing( results ):
      mcp.setResults( ( 'Error with %s-setup\n' % state[ 'target' ] ) + '\n'.join( results ) )
      return False

  logging.info( 'iterate: executing target "%s"' % state[ 'target' ] )
  ( target_results, rc ) = execute_lines_rc( '%s %s %s' % ( MAKE_CMD, state[ 'target' ], ' '.join( args ) ), state[ 'dir' ] )
  if rc != 0:
    if rc == 2 and _makeDidNothing( target_results ):
      mcp.setResults( None )
      return True

    else:
      mcp.setResults( ( 'Error with target %s\n' % state[ 'target' ] ) + '\n'.join( target_results ) )
      return False

  if _makeDidNothing( target_results ):
    mcp.setResults( None )
    return True
  else:
    mcp.setResults( '\n'.join( target_results ) )

  score_list = []
  for line in target_results:
    match = SCORE_RE.search( line )
    if match:
      score_list.append( match.group( 1 ) )

  if len( score_list ) > 0:
    mcp.setScore( sum( score_list ) / len( score_list ) )
  else:
    mcp.setScore( None )

  # if docs, upload to confluence
  if state == 'docs':
    if rc != 0 or len( results ) == 0:
      mcp.setResults( ( 'Error getting %s-file\n' % state[ 'target' ] ) + '\n'.join( results ) )
      return False

    filename_list = []
    for line in results:
      filename_list += line.split()

    for filename in filename_list:
      ( local_filename, confluence_filename ) = filename.split( ':' )
      uploadToConfluence( config, local_filename, confluence_filename  )

  # if package/resource upload to packrat
  if _isPackageBuild( state ):
    logging.info( 'iterate: getting package file "%s"' % state[ 'target' ] )
    mcp.sendStatus( 'Package Build' )
    ( results, rc ) = execute_lines_rc( '%s -s %s-file %s' % ( MAKE_CMD, state[ 'target' ], ' '.join( args ) ), state[ 'dir' ] )
    if rc != 0 or len( results ) == 0:
      mcp.setResults( ( 'Error getting %s-file\n' % state[ 'target' ] ) + '\n'.join( results ) )
      return False

    package_file_list = []
    filename_list = []
    for line in results:
      filename_list += line.split()

    for filename in filename_list:
      try:
        ( filename, version ) = filename.split( ':' )
      except ValueError:
        version = None

      if filename[0] != '/': #it's not an aboslute path, prefix is with the working dir
        filename = os.path.realpath( os.path.join( state[ 'dir' ], filename ) )

      if packrat.checkFileName( os.path.basename( filename ) ):
        mcp.setResults( 'Filename "%s" is allready in use in packrat, skipping the file in upload.' % os.path.basename( filename ) )
        logging.warning( 'Filename ""%s" allready on packrat, skipping...' % os.path.basename( filename ) )
        target_results.append( '=== File "%s" skipped.' % os.path.basename( filename ) )
        continue

      logging.info( 'iterate: uploading "%s"' % filename )
      src = open( filename, 'r' )
      try:
        result = packrat.addPackageFile( src, 'Package File "%s"' % os.path.basename( filename ), 'MCP Auto Build from %s.  Build on %s at %s' % ( state[ 'url' ], socket.getfqdn(), datetime.utcnow() ), version )

      except Exception as e:
        logging.exception( 'iterate: Exception "%s" while adding package file "%s"' % ( e, filename ) )
        mcp.uploadedPackages( package_file_list )
        mcp.setResults( 'Exception adding package file "%s"' % filename )
        src.close()
        return False

      src.close()

      if isinstance( result, list ):
        raise Exception( 'Packrat was unable to detect distro, options are "%s"' % result )

      target_results.append( '=== File "%s" uploaded.' % os.path.basename( filename ) )
      package_file_list.append( os.path.basename( filename ) )

      if result is not None:
        mcp.sendStatus( 'Packge(s) NOT (all) Uploaded: result "%s"' % result )
        mcp.uploadedPackages( package_file_list )
        mcp.setResults( '\n'.join( target_results ) )
        return False

      if not packrat.checkFileName( os.path.basename( filename ) ):
        raise Exception( 'Recently added file "%s" not showing in packrat.' % os.path.basename( filename ) )

    packrat.logout()

    mcp.sendStatus( 'Package(s) Uploaded' )
    mcp.uploadedPackages( package_file_list )
    mcp.setResults( '\n'.join( target_results ) )

  return True
