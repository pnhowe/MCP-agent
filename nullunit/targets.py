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

  package_file_list = []
  filename_list = []
  for line in results:
    filename_list += line.split()

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
      mcp.setResults( state[ 'target' ], 'Filename "{0}" is allready in use in packrat, skipping the file in upload.'.format( os.path.basename( filename ) ) )
      logging.warn( 'targets: filename "{0}" allready on packrat, skipping...'.format( os.path.basename( filename ) ) )
      target_results.append( '=== File "{0}" skipped.'.format( os.path.basename( filename ) ) )
      continue

    logging.info( 'iterate: uploading "{0}"'.format( filename ) )
    src = open( filename, 'rb' )
    try:
      result = packrat.addPackageFile(
                                       src,
                                       'Package File "{0}"'.format( os.path.basename( filename ) ),
                                       'MCP Auto Build from {0}.  Build on {1} at {2}'.format( state[ 'url' ], socket.getfqdn(), datetime.utcnow() ),
                                       distroversion,
                                       file_type
                                     )

    except Exception as e:
      result = e

    finally:
      src.close()

    if isinstance( result, list ):
      raise Exception( 'Packrat was unable to detect distro, options are "{0}"'.format( result ) )

    if result is not None:
      mcp.sendMessage( 'Packge(s) NOT (all) Uploaded: result "{0}"'.format( result ) )
      mcp.setResults( state[ 'target' ], '\n'.join( target_results ) )  # yes we do it a second time, now it has the files uploaded appended
      mcp.uploadedPackages( package_file_list )
      return False

    target_results.append( '=== File "{0}" uploaded.'.format( os.path.basename( filename ) ) )
    package_file_list.append( os.path.basename( filename ) )

  for package_file in package_file_list:
    if not packrat.checkFileName( package_file ):
      raise Exception( 'Recently added file "{0}" not showing in packrat.'.format( package_file ) )

  mcp.setResults( state[ 'target' ], '\n'.join( target_results ) )  # yes we do it a second time, now it has the files uploaded appended
  mcp.uploadedPackages( package_file_list )

  return True


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
