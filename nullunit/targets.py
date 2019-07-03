import logging
import socket
import os
from datetime import datetime
from nullunit.common import runMake, MakeException
from nullunit.scoring import extractScore


def testTarget( state, mcp, args, extra_env ):
  logging.info( 'targets: executing target lint' )
  mcp.sendMessage( 'Running Lint' )
  try:
    lint_results = runMake( 'lint {0}'.format( ' '.join( args ) ), state[ 'dir' ], extra_env )
  except MakeException as e:
    logging.warn( 'targets: error with lint' )
    mcp.setResults( 'lint', 'Error with target lint: "{0}"'.format( e ) )
    return False

  mcp.setScore( 'lint', extractScore( lint_results ) )
  mcp.setResults( 'lint', '\n'.join( lint_results ) )

  logging.info( 'targets: executing target test' )
  mcp.sendMessage( 'Running Test' )
  try:
    test_results = runMake( 'test {0}'.format( ' '.join( args ) ), state[ 'dir' ], extra_env )
  except MakeException as e:
    logging.warn( 'targets: error with test' )
    mcp.setResults( 'test', 'Error with target test: "{0}"'.format( e ) )
    return False

  mcp.setScore( 'test', extractScore( test_results ) )
  mcp.setResults( 'test', '\n'.join( test_results ) )

  return True


def buildTarget( state, mcp, packrat, args, extra_env, store_packages, num_jobs ):
  logging.info( 'targets: executing target build - "{0}"'.format( state[ 'target' ] ) )
  mcp.sendMessage( 'Building Package(s)' )
  try:
    target_results = runMake( '{0} -j{1} {2}'.format( state[ 'target' ], num_jobs, ' '.join( args ) ), state[ 'dir' ], extra_env=extra_env )
  except MakeException as e:
    logging.warn( 'targets: error with build - "{0}"'.format( state[ 'target' ] ) )
    mcp.setResults( state[ 'target' ], 'Error with target build - "{0}": "{1}"'.format( state[ 'target' ], e ) )
    return False

  mcp.setResults( state[ 'target' ], '\n'.join( target_results ) )

  logging.info( 'iterate: getting package file "{0}"'.format( state[ 'target' ] ) )

  if not store_packages:
    return True

  try:
    results = runMake( '-s {0}-file {1}'.format( state[ 'target' ], ' '.join( args ) ), state[ 'dir' ] )
  except MakeException as e:
    logging.warn( 'targets: error with "{0}"-file'.format( state[ 'target' ] ) )
    mcp.setResults( state[ 'target' ], 'Error getting {0}-file: {1}'.format( state[ 'target' ], e ) )
    return False

  filename_list = []
  for line in results:
    filename_list += line.split()

  status_map = {}
  mcp.sendMessage( 'Uploading Package(s)' )
  for filename in filename_list:
    parts = filename.split( ':' )
    filename = parts.pop( 0 )
    try:
      distroversion = parts.pop( 0 )
    except IndexError:
      distroversion = None

    try:
      file_type = parts.pop( 0 )
    except IndexError:
      file_type = None

    if filename[0] != '/':  # it's not an aboslute path, prefix is with the working dir
      filename = os.path.realpath( os.path.join( state[ 'dir' ], filename ) )

    if packrat.checkFileName( os.path.basename( filename ) ):
      status_map[ filename ] = '*EXISTS*'
      continue

    logging.info( 'iterate: uploading "{0}"'.format( filename ) )
    src = open( filename, 'rb' )
    try:
      status_map[ os.path.basename( filename ) ] = packrat.addPackageFile(
                                       src,
                                       'Package File "{0}"'.format( os.path.basename( filename ) ),
                                       'MCP Auto Build from {0}.  Build on {1} at {2}'.format( state[ 'url' ], socket.getfqdn(), datetime.utcnow() ),
                                       distroversion,
                                       file_type
                                     )

    except Exception as e:
      status_map[ os.path.basename( filename ) ] = e

    finally:
      src.close()

  package_file_map = {}

  result = True
  for filename, status in status_map.items():
    if isinstance( status, list ):
      logging.warn( 'targets: Packrat was unable to detect distro for "{0}", options are "{1}".'.format( filename, status ) )
      target_results.append( '=== File "{0}" Unable to Detect Distro, options "{1}", skipped.'.format( filename, status ) )
      result = False

    elif isinstance( status, Exception ):
      status = str( status )
      logging.warn( 'targets: filename "{0}" erroro uploading: "{1}", skipped.'.format( filename, status ) )
      target_results.append( '=== File "{0}" Error Uploading: "{1}", skipped.'.format( filename, status ) )
      result = False

    elif status == '*EXISTS*':
      logging.warn( 'targets: filename "{0}" allready on packrat, skipped.'.format( filename ) )
      target_results.append( '=== File "{0}" Allready Exists, skipped.'.format( filename ) )

    else:
      logging.info( 'targets: filename "{0}" uploaded.'.format( filename ) )
      target_results.append( '=== File "{0}" uploaded.'.format( filename ) )
      package_file_map[ filename ] = status

  if result:
    mcp.sendMessage( 'No Errors uploading Files' )
  else:
    mcp.sendMessage( '"{0}" of "{1}" Files did not upload, see results for details'.format( len( status_map ) - len( package_file_map ), len( status_map ) ) )

  mcp.setResults( state[ 'target' ], '\n'.join( target_results ) )  # update results now that we have upload status
  mcp.uploadedPackages( package_file_map )

  return result


def docTarget( state, mcp, confluence, args, extra_env ):
  logging.info( 'targets: executing target "{0}"'.format( state[ 'target' ] ) )
  try:
    target_results = runMake( 'doc {0}'.format( ' '.join( args ) ), state[ 'dir' ], extra_env=extra_env )
  except MakeException as e:
    mcp.setResults( 'doc', 'Error with target doc: {0}'.format( e ) )
    return False

  mcp.setResults( 'doc', '\n'.join( target_results ) )
  try:
    results = runMake( '-s doc-file {0}'.format( ' '.join( args ) ), state[ 'dir' ] )
  except MakeException as e:
    logging.warn( 'targets: error with doc-file' )
    mcp.setResults( 'doc', 'Error getting doc-file: {0}'.format( e ) )
    return False

  filename_list = []
  for line in results:
    filename_list += line.split()

  for filename in filename_list:
    ( local_filename, confluence_filename ) = filename.split( ':' )
    confluence.upload( local_filename, confluence_filename )

  return True


def otherTarget( state, mcp, args, extra_env ):
  logging.info( 'targets: executing target "{0}"'.format( state[ 'target' ] ) )
  try:
    target_results = runMake( '{0} {1}'.format( state[ 'target' ], ' '.join( args ) ), state[ 'dir' ], extra_env=extra_env )
  except MakeException as e:
    logging.warn( 'targets: error with target "{0}"'.format( state[ 'target' ] ) )
    mcp.setResults( state[ 'target' ], 'Error with target {0}: {1}'.format( state[ 'target' ], e ) )
    return False

  mcp.setResults( state[ 'target' ], '\n'.join( target_results ) )

  return True
