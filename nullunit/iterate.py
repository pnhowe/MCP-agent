import json
import os
import glob
import shutil
import logging
import time
import itertools
from nullunit.common import GIT_CMD, WORK_DIR, PACKAGE_MANAGER, getPackrat, getContractor, runMake, MakeException
from nullunit.procutils import execute, ExecutionException
from nullunit.targets import testTarget, buildTarget, docTarget, otherTarget


def _makeAndGetValues( mcp, state, target, args, extra_env ):
  try:
    item_list = runMake( '-s {0} {1}'.format( target, ' '.join( args ) ), state[ 'dir' ], extra_env=extra_env )
  except MakeException as e:
    logging.warn( 'iterate: error getting requires' )
    mcp.setResults( state[ 'target' ], 'Error getting requires: "{0}"'.format( e ) )
    return None

  results = []
  for item in item_list:
    if item.startswith( 'make:' ) or item.startswith( 'make[' ):  # make was unhappy about something, skip that line.... if it was important, it will come out later
      continue

    item = item.strip()
    if item:
      results.append( item  )

  return results


def _isPackageBuild( target ):
  return target in ( 'dpkg', 'rpm', 'respkg', 'resource' )


def _isPackageTestDoc( target ):
  return _isPackageBuild( target ) or target in ( 'test', 'doc' )


def readState( file ):
  try:
    state = json.loads( open( file, 'r' ).read() )
  except Exception:
    return None

  return state


def writeState( file, state ):
  open( file, 'w' ).write( json.dumps( state ) )


def doStep( state, mcp, config, num_jobs ):
  start_state = state[ 'state' ]
  mcp.sendMessage( 'Executing Stage "{0}"'.format( start_state ) )
  logging.info( 'iterate: Executing Stage "{0}"'.format( start_state ) )

  if start_state == 'clone':
    state[ 'dir' ] = doClone( state, config )
    state[ 'state' ] = 'checkout'

  elif start_state == 'checkout':
    doCheckout( state )
    state[ 'state' ] = 'requires'

  elif start_state == 'requires':
    if doRequires( state, mcp, config ):
      state[ 'state' ] = 'clean'
    else:
      state[ 'state' ] = 'failed'
      mcp.setSuccess( False )

  elif start_state == 'clean':
    if doClean( state, mcp ):
      state[ 'state' ] = 'target'
    else:
      state[ 'state' ] = 'failed'
      mcp.setSuccess( False )

  elif start_state == 'target':
    if doTarget( state, mcp, config, num_jobs ):
      state[ 'state' ] = 'done'
      mcp.setSuccess( True )
    else:
      state[ 'state' ] = 'failed'
      mcp.setSuccess( False )

  else:
    raise Exception( 'Unknown state "{0}"'.format( start_state ) )

  mcp.sendMessage( 'Stage "{0}" Complete'.format( start_state ) )
  logging.info( 'iterate: Stage "{0}" Complete'.format( start_state ) )


def doClone( state, config ):
  try:
    os.makedirs( WORK_DIR )

  except OSError as e:
    if e.errno == 17:  # allready exists
      shutil.rmtree( WORK_DIR )
      os.makedirs( WORK_DIR )

    else:
      raise e

  extra_env = {}
  git_proxy = config.get( 'git', 'proxy' )
  if not git_proxy:
    extra_env[ 'http_proxy' ] = ''
    extra_env[ 'https_proxy' ] = ''
  else:
    extra_env[ 'http_proxy' ] = git_proxy
    extra_env[ 'https_proxy' ] = git_proxy

  logging.info( 'iterate: cloning "{0}"'.format( state[ 'url' ] ) )
  try:
    execute( '{0} clone {1}'.format( GIT_CMD, state[ 'url' ] ), WORK_DIR, extra_env=extra_env )
  except ExecutionException as e:
    logging.error( 'ExecutionException "{0}" while cloning'.format( e ) )
    raise Exception( 'Exception "{0}" while cloning'.format( e ) )

  return glob.glob( '{0}/*'.format( WORK_DIR ) )[0]


def doCheckout( state ):
  logging.info( 'iterate: checking out "{0}"'.format( state[ 'branch' ] ) )
  try:
    execute( '{0} checkout {1}'.format( GIT_CMD, state[ 'branch' ] ), state[ 'dir' ] )
  except ExecutionException as e:
    logging.error( 'ExecutionException "{0}" while cloning'.format( e ) )
    raise Exception( 'Exception "{0}" while cloning'.format( e ) )

  tmp = int( time.time() ) - ( 3600 * 24 )  # hopfully nothing is clock skewed more than this
  times = ( tmp, tmp )

  for ( root, dirname_list, filename_list ) in os.walk( state[ 'dir' ] ):  # go through and `touch` everything.
    for filename in filename_list:
      try:                                                                   # clock skew is a fact of life, we are building everything anyway
        os.utime( os.path.join( root, filename ), times )                    # this helps make not complain about the future
      except OSError:
        pass


def doClean( state, mcp ):
  logging.info( 'iterate: executing clean' )

  try:
    runMake( 'clean', state[ 'dir' ] )
  except MakeException as e:
    logging.warn( 'iterate: Error with clean' )
    mcp.setResults( state[ 'target' ], 'Error with clean: "{0}"'.format( e ) )
    return False

  return True


def doRequires( state, mcp, config ):
  logging.info( 'iterate: getting requires for "{0}"'.format( state[ 'target' ] ) )
  args = []
  args.append( 'NULLUNIT=1' )

  extra_env = {}
  extra_env[ 'DEBIAN_PRIORITY' ] = 'critical'
  extra_env[ 'DEBIAN_FRONTEND' ] = 'noninteractive'

  if not _isPackageTestDoc( state[ 'target' ] ):
    values = {}
    args.append( 'RESOURCE_NAME="{0}"'.format( config.get( 'mcp', 'resource_name' ) ) )
    args.append( 'RESOURCE_INDEX={0}'.format( config.get( 'mcp', 'resource_index' ) ) )
    item_list = _makeAndGetValues( mcp, state, '{0}-config'.format( state[ 'target' ] ), args, extra_env )
    if item_list is None:
      return False

    for item in item_list:
      ( key, value ) = item.split( ':', 1 )
      if len( value ) > 1 and value[0] in ( '[', '{' ):
        value = json.loads( value )

      values[ key ] = value

    if values:
      contractor = getContractor( mcp )

      if not contractor.updateConfig( config.get( 'mcp', 'structure_id' ), values ):
        raise Exception( 'iterate: Error Setting Configuration Vaules' )

  required_list = _makeAndGetValues( mcp, state, '{0}-requires'.format( state[ 'target' ] ), args, extra_env )
  if required_list is None:
    return False

  required_list = list( set( itertools.chain.from_iterable( [ i.split() for i in required_list ] ) ) )

  if not required_list:
    return True

  logging.info( 'iterate: updating pkg metadata' )
  try:
    if PACKAGE_MANAGER == 'apt':
      execute( '/usr/bin/apt-get update' )
    elif PACKAGE_MANAGER == 'yum':
      execute( '/usr/bin/yum clean all' )
    else:
      raise Exception( 'Unknown Package manager "{0}"'.format( PACKAGE_MANAGER ) )

  except ExecutionException:
    logging.error( 'ExecutionException "{0}" while updating packaging info for required packages' )
    raise Exception( 'Exception "{0}" while updating packaging info for required packages' )

  logging.info( 'iterate: installing "{0}"'.format( required_list ) )
  try:
    if PACKAGE_MANAGER == 'apt':
      execute( '/usr/bin/apt-get install -y {0}'.format( ' '.join( required_list ) ) )
    elif PACKAGE_MANAGER == 'yum':
      execute( '/usr/bin/yum install -y {0}'.format( ' '.join( required_list ) ) )
      for required in required_list:
        execute( '/usr/bin/rpm --query {0}'.format( required ) )
    else:
      raise Exception( 'Unknown Package manager "{0}"'.format( PACKAGE_MANAGER ) )

  except ExecutionException as e:
    logging.error( 'ExecutionException "{0}" while installing required packages'.format( e ) )
    raise Exception( 'Exception "{0}" while installing required packages'.format( e ) )

  return True


def doTarget( state, mcp, config, num_jobs ):
  args = []
  args.append( 'NULLUNIT=1' )
  args.append( 'BUILD_NAME={0}'.format( config.get( 'mcp', 'build_name' ) ) )

  extra_env = {}
  proxy = config.get( 'misc', 'proxy_env_var' )
  if not proxy:
    extra_env[ 'http_proxy' ] = ''
    extra_env[ 'https_proxy' ] = ''
  else:
    extra_env[ 'http_proxy' ] = proxy
    extra_env[ 'https_proxy' ] = proxy

  if not _isPackageTestDoc( state[ 'target' ] ):
    args.append( 'RESOURCE_NAME="{0}"'.format( config.get( 'mcp', 'resource_name' ) ) )
    args.append( 'RESOURCE_INDEX={0}'.format( config.get( 'mcp', 'resource_index' ) ) )

  logging.info( 'iterate: executing setup "{0}"'.format( state[ 'target' ] ) )

  try:
    runMake( '{0}-setup {1}'.format( state[ 'target' ], ' '.join( args ) ), state[ 'dir' ], extra_env=extra_env )
  except MakeException as e:
    logging.warn( 'iterate: with "{0}"-setup'.format( state[ 'target' ] ) )
    mcp.setResults( state[ 'target' ], 'Error with "{0}"-setup: "{1}"'.format( state[ 'target' ], e ) )
    return False

  if state[ 'target' ] == 'test':
    return testTarget( state, mcp, args, extra_env )

  elif _isPackageBuild( state[ 'target'] ):
    packrat = getPackrat( config )  # connect to Packrat first, just in case there is a problem, then we know right up front
    if not packrat:
      raise Exception( 'iterate: Error Connecting to packrat' )

    try:
      return buildTarget( state, mcp, packrat, args, extra_env, config.getboolean( 'mcp', 'store_packages' ), num_jobs )
    finally:
      packrat.logout()

  elif state[ 'target' ] == 'doc':
    confluence = None
    return docTarget( state, mcp, confluence, args, extra_env )

  return otherTarget( state, mcp, args, extra_env )
