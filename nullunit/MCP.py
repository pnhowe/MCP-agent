import logging
import time
import random
import math

from cinp import client

MCP_API_VERSIONS = ( '0.9', '0.10' )

# TODO: move backoff delay and retries to cinp client
DELAY_MULTIPLIER = 15
# delay of 15 results in a delay of:
# min delay = 0, 10, 16, 20, 24, 26, 29, 31, 32, 34, 35, 37, 38, 39, 40 ....
# max delay = 0, 20, 32, 40, 48, 52, 58, 62, 64, 68, 70, 74, 76, 78, 80 .....


def _backOffDelay( count ):
  if count < 1:  # math.log dosen't do so well below 1
    count = 1

  if count > 20:  # really don't need to get any more delaied than this
    count = 20

  factor = int( DELAY_MULTIPLIER * math.log( count ) )
  delay = int( factor + ( random.random() * factor ) )
  logging.debug( 'MCP: sleeping for "{0}"'.format( delay ) )
  time.sleep( delay )


class MCP( object ):
  def __init__( self, host, proxy, job_id, instance_id, cookie ):
    self.cinp = client.CInP( host, '/api/v1/', proxy )
    self.job_id = job_id
    self.instance_id = instance_id
    self.cookie = cookie

    count = 0
    while True:
      count += 1
      try:
        root = self.cinp.describe( '/api/v1/' )
        break
      except ( client.Timeout, client.ResponseError ):
        _backOffDelay( count )
        logging.warn( 'MCP: getRequest: retry {0}'.format( count ) )

    if root[ 'api-version' ] not in MCP_API_VERSIONS:
      raise Exception( 'Expected API version (one of) "{0}" found "{1}"'.format( MCP_API_VERSIONS, root[ 'api-version' ] ) )

  def contractorInfo( self ):
    logging.info( 'MCP: Get Contractor Info' )
    info = self.cinp.call( '/api/v1/config(getContractorInfo)', {} )

    return { 'host': info[ 'host' ], 'proxy': self.cinp.proxy }

  def signalJobRan( self ):
    logging.info( 'MCP: Signal Job Ran' )
    self.cinp.call( '/api/v1/Processor/Instance:{0}:(jobRan)'.format( self.instance_id ), { 'cookie': self.cookie } )

  def sendMessage( self, message ):
    logging.info( 'MCP: Message "{0}"'.format( message ) )
    self.cinp.call( '/api/v1/Processor/Instance:{0}:(setMessage)'.format( self.instance_id ), { 'cookie': self.cookie, 'message': message } )

  def setSuccess( self, success ):
    logging.info( 'MCP: Success "{0}"'.format( success ) )
    self.cinp.call( '/api/v1/Processor/Instance:{0}:(setSuccess)'.format( self.instance_id ), { 'cookie': self.cookie, 'success': success } )

  def setResults( self, target, results ):
    if results is not None:
      logging.info( 'MCP: Results "{0}"'.format( results[ -100: ].strip() ) )
    else:
      logging.info( 'MCP: Results <empty>' )

    self.cinp.call( '/api/v1/Processor/Instance:{0}:(setResults)'.format( self.instance_id ), { 'cookie': self.cookie, 'target': target, 'results': results } )

  def setScore( self, target, score ):
    if score is not None:
      logging.info( 'MCP: Score "{0}"'.format( score ) )
    else:
      logging.info( 'MCP: Score <undefined>' )

    self.cinp.call( '/api/v1/Processor/Instance:{0}:(setScore)'.format( self.instance_id ), { 'cookie': self.cookie, 'target': target, 'score': score } )

  def uploadedPackages( self, package_file_map ):
    if not package_file_map:
      return

    self.cinp.call( '/api/v1/Processor/Instance:{0}:(addPackageFiles)'.format( self.instance_id ), { 'cookie': self.cookie, 'package_file_map': package_file_map } )

  def getInstanceState( self, name=None ):
    logging.info( 'MCP: Instance State for "{0}"'.format( name ) )
    args = {}
    if name is not None:
      args[ 'name' ] = name

    # json encoding turns the numeric dict keys into strings, this will undo that  # TODO:  this is fixed in CInP now??
    result = {}
    state_map = self.cinp.call( '/api/v1/Processor/BuildJob:{0}:(getInstanceState)'.format( self.job_id ), args )
    if name is None:
      for name in state_map:
        result[ name ] = {}
        for index, state in state_map[ name ].items():
          result[ name ][ int( index ) ] = state
    else:
      for index, state in state_map.items():
        result[ int( index ) ] = state

    return result

  def getInstanceDetail( self, name=None ):
    logging.info( 'MCP: Instance Detail for "{0}"'.format( name ) )
    args = {}
    if name is not None:
      args[ 'name' ] = name

    # json encoding turns the numeric dict keys into strings, this will undo that
    result = {}
    detail_map = self.cinp.call( '/api/v1/Processor/BuildJob:{0}:(getInstanceDetail)'.format( self.job_id ), args )
    if name is None:
      for name in detail_map:
        result[ name ] = {}
        for index, detail in detail_map[ name ].items():
          result[ name ][ int( index ) ] = detail
    else:
      for index, detail in detail_map.items():
        result[ int( index ) ] = detail

    return result

  def updateValueMap( self, value_map  ):
    logging.info( 'MCP: Setting Value "{0}"'.format( value_map ) )

    self.cinp.call( '/api/v1/Processor/Instance:{0}:(updateValueMap)'.format( self.instance_id ), { 'cookie': self.cookie, 'value_map': value_map } )

    return True

  def getValueMap( self, name=None ):
    logging.info( 'MCP: Getting Value Map' )

    return self.cinp.call( '/api/v1/Processor/Instance:{0}:(getValueMap)'.format( self.instance_id ), { 'cookie': self.cookie } )
