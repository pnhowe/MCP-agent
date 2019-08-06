import configparser
import logging
import re
import os

from nullunit.MCP import MCP
from nullunit.Contractor import Contractor
from nullunit.Packrat import Packrat
from nullunit.Confluence import Confluence
from nullunit.procutils import execute_lines_rc


CONFIG_FILE = '/etc/nullunit.conf'
MAKE_CMD = '/usr/bin/make'
GIT_CMD = '/usr/bin/git'
WORK_DIR = '/nullunit/src'  # if the dir is a ends in src, it will make go and it's GOPATH happy

if os.path.exists( '/usr/bin/apt-get' ):
  PACKAGE_MANAGER = 'apt'
elif os.path.exists( '/usr/bin/yum' ):
  PACKAGE_MANAGER = 'yum'
else:
  raise Exception( 'Unable to detect package manager' )

# make sure something like "make: *** No rule to make target `XXXX', needed by `XXXX'.  Stop." still fails
DIDNOTHING_RE_LIST = [ re.compile( '^make(\[[0-9]+\])?: \*\*\* No rule to make .* Stop\.$' ), re.compile( '^make(\[[0-9]+\])?: Nothing to be done for .*\.$' ) ]


def makeDidNothing( results ):
  if len( results ) != 1:
    return False

  for item in DIDNOTHING_RE_LIST:
    if item.search( results[0] ):
      return True

  return False


class MakeException( Exception ):
  pass


def runMake( cmd, dir, extra_env=None ):
  ( results, rc ) = execute_lines_rc( '{0} {1}'.format( MAKE_CMD, cmd ), dir, extra_env=extra_env )

  if rc == 0:
    return results

  if rc == 2 and makeDidNothing( results ):
    return []

  raise MakeException( 'Error running make with "{0}", rc: "{1}"'.format( cmd, rc ) + '\n'.join( results ) )


def getConfig():
  config = configparser.ConfigParser( interpolation=None )

  try:
    config.read( CONFIG_FILE )
  except configparser.Error as e:
    logging.error( 'Error reading config file: {0}'.format( e ) )
    return None

  return config


def getMCP( config ):
  try:
    return MCP( config.get( 'mcp', 'host' ), config.get( 'mcp', 'proxy' ), config.getint( 'mcp', 'job_id' ), config.getint( 'mcp', 'instance_id' ), config.get( 'mcp', 'instance_cookie' ) )
  except configparser.Error:
    logging.error( 'Error retreiving MCP host, proxy, job_id, instance_id, and/or instance_cookie from config file.' )
    return None


def getContractor( mcp ):
  info = mcp.contractorInfo()

  return Contractor( info[ 'host' ], info[ 'proxy' ] )


def getPackrat( config ):
  try:
    return Packrat( config.get( 'packrat', 'host' ), config.get( 'packrat', 'proxy' ), config.get( 'packrat', 'username' ), config.get( 'packrat', 'password' ) )
  except configparser.Error:
    logging.error( 'Error retreiving Packrat host, and/or proxy from config file' )
    return None


def getConfluence( config ):
  try:
    return Confluence( config.get( 'confluence', 'host' ), config.get( 'confluence', 'proxy' ), config.get( 'confluence', 'username' ), config.get( 'confluence', 'password' ) )
  except configparser.Error:
    logging.error( 'Error retreiving Confluence host, and/or proxy from config file' )
    return None
