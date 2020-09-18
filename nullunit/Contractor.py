import logging

from cinp import client

API_VERSION = '0.9'


class Contractor( object ):
  def __init__( self, host, proxy ):
    self.cinp = client.CInP( host, '/api/v1/', proxy )

    # not doing backOffDelay, assuming the one for MCP covers this too
    root = self.cinp.describe( '/api/v1/' )

    if root[ 'api-version' ] != API_VERSION:
      raise Exception( 'Expected API version "{0}" found "{1}"'.format( API_VERSION, root[ 'api-version' ] ) )

  def getConfig( self, structure_id_list ):
    if not structure_id_list:
      return {}

    logging.info( 'Contractor: getConfig for "{0}"'.format( structure_id_list ) )
    return self.cinp.call( '/api/v1/Building/Structure:{0}:(getConfig)'.format( ':'.join( [ str( i ) for i in structure_id_list ] ) ), {}, force_multi_mode=True )

  def updateConfig( self, structure_id, config_value_map ):
    logging.info( 'Contractor: setConfigValues for "{0}"'.format( structure_id ) )
    return self.cinp.call( '/api/v1/Building/Structure:{0}:(updateConfig)'.format( structure_id ), { 'config_value_map': config_value_map } )
