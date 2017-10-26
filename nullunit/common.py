import ConfigParser
import logging

from nullunit.MCP import MCP
from nullunit.Packrat import Packrat

CONFIG_FILE = '/etc/mcp/nullunit.conf'


def getConfig():
  config = ConfigParser.ConfigParser()

  try:
    config.read( CONFIG_FILE )
  except ConfigParser.Error as e:
    logging.error( 'Error reading config file: %s' % e )
    return None

  return config


def getMCP( config ):
  try:
    return MCP( config.get( 'mcp', 'host' ), config.get( 'mcp', 'proxy' ), config.getint( 'mcp', 'job_id' ), config.get( 'mcp', 'resource_name' ), config.getint( 'mcp', 'resource_index' ) )
  except ConfigParser.Error:
    logging.error( 'Error retreiving MCP host, proxy, job_id, resource_name, and/or resource_index from config file.' )
    return None


def getPackrat( config ):
  try:
    return Packrat( config.get( 'packrat', 'host' ), config.get( 'packrat', 'proxy' ), config.get( 'packrat', 'name' ), config.get( 'packrat', 'psk' ) )
  except ConfigParser.Error:
    logging.error( 'Error retreiving Packrat host, and/or proxy from config file' )
    return None
