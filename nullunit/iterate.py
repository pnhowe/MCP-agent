import json
import os
import glob
import shutil
import logging
import socket
from datetime import datetime

from procutils import execute, execute_lines


GIT_CMD = '/usr/bin/git'
MAKE_CMD = '/usr/bin/make'
WRK_DIR = '/nullunit'
APT_GET_CMD = '/usr/bin/apt-get'

def _makeDidNotthing( results ):
  return len( results ) == 1 and ( results[0].startswith( 'make: Nothing to be done' ) or results[0].startswith( 'make: *** No rule to make' ) )

def readState( file ):
  try:
    state = json.loads( open( file, 'r' ).read() )
  except:
    return None

  return state


def writeState( file, state ):
  open( file, 'w' ).write( json.dumps( state ) )


def doStep( state, mcp, packrat ):
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
    doRequires( state )
    state[ 'state' ] = 'target'

  elif start_state == 'target':
    if doTarget( state, packrat, mcp ):
      state[ 'state' ] = 'done'
      mcp.setSuccess( True )

    else:
      state[ 'state' ] = 'failed'
      mcp.setSuccess( False )

  mcp.sendStatus( 'Stage "%s" Complete' % start_state )
  logging.info( 'iterate: Stage "%s" Complete' % start_state )


def doClone( state ):
  try:
    os.makedirs( WRK_DIR )
  except OSError as e:
    if e.errno == 17: # allready exists
      shutil.rmtree( WRK_DIR )
      os.makedirs( WRK_DIR )

    else:
      raise e

  logging.info( 'iterate: cloning "%s"' % state[ 'url' ] )
  execute( '%s clone %s' % ( GIT_CMD, state[ 'url' ] ), WRK_DIR )
  return glob.glob( '%s/*' % WRK_DIR )[0]


def doCheckout( state ):
  logging.info( 'iterate: checking out "%s"' % state[ 'branch' ] )
  execute( '%s checkout %s' % ( GIT_CMD, state[ 'branch' ] ), state[ 'dir' ] )


def doRequires( state ):
  logging.info( 'iterate: getting requires "%s"' % state[ 'requires' ] )
  env = os.environ
  env['DEBIAN_PRIORITY'] = 'critical'
  env['DEBIAN_FRONTEND'] = 'noninteractive'
  results = execute_lines( '%s %s' % ( MAKE_CMD, state[ 'requires' ] ), state[ 'dir' ], env=env, ok_rc=[ 0, 2 ] )

  if _makeDidNotthing( results ):
    return

  for required in results:
    required = required.strip()
    if not required:
      continue

    logging.info( 'iterate: installing "%s"' % required )
    execute( '%s install -y %s' % ( APT_GET_CMD, required ) )


def doTarget( state, packrat, mcp ):
  logging.info( 'iterate: executing target "%s"' % state[ 'target' ] )
  results = execute_lines( '%s %s' % ( MAKE_CMD, state[ 'target' ] ), state[ 'dir' ], ok_rc=[ 0, 2 ] )

  if _makeDidNotthing( results ):
    mcp.setResults( '' )
    return True

  mcp.setResults( '\n'.join( results ) )

  if state[ 'target' ] in ( 'dpkg', 'rpm', 'resource' ):
    logging.info( 'iterate: getting package file "%s"' % state[ 'requires' ] )
    mcp.sendStatus( 'Package Build' )
    results = execute_lines( '%s %s-file' % ( MAKE_CMD, state[ 'target' ] ), state[ 'dir' ], ok_rc=[ 0, 2 ] )
    if not results or _makeDidNotthing( results ):
      raise Exception( 'package target did not return a file to upload' )

    for file_name in results:
      file_name = os.path.join( state[ 'dir' ], file_name )
      logging.info( 'iterate: uploading "%s"' % file_name )
      src = open( file_name, 'r' )
      try:
        result = packrat.addPackageFile( src, 'Package File "%s"' % os.path.basename( file_name ), 'MCP Auto Build from %s.  Build on %s at %s' % ( state[ 'url' ], socket.getfqdn(), datetime.utcnow() ) )
      except Exception as e:
        logging.exception( 'iterate: Exception "%s" while adding package file "%s"' % ( e, file_name ) )
        mcp.setResults( 'Exception adding package file' )
        src.close()
        return False

      src.close()
      if not result:
        mcp.sendStatus( 'Packge(s) NOT (all) Uploaded' )
        return False

    mcp.sendStatus( 'Package(s) Uploaded' )

  return True
