import logging

from cinp import client

class MCP( object ):
  def __init__( self, host, proxy, job_id, name, index ):
    self.cinp = client.CInP( host, '/api/v1', proxy )
    self.job_id = job_id
    self.name = name
    self.index = index

  def signalJobRan( self ):
    logging.info( 'MCP: Signal Job Ran' )
    self.cinp.call( '/api/v1/Processor/BuildJob:%s:(jobRan)' % self.job_id, {} )

  def sendStatus( self, status ):
    logging.info( 'MCP: Status "%s"' % status )
    self.cinp.call( '/api/v1/Processor/BuildJob:%s:(updateResourceState)' % self.job_id, { 'name': self.name, 'index': self.index, 'status': status } )

  def setSuccess( self, success ):
    logging.info( 'MCP: Success "%s"' % success )
    self.cinp.call( '/api/v1/Processor/BuildJob:%s:(setResourceSuccess)' % self.job_id, { 'name': self.name, 'index': self.index, 'success': success } )

  def setResults( self, results ):
    if results is not None:
      logging.info( 'MCP: Results "%s"' % results[ -100: ].strip() )
    else:
      logging.info( 'MCP: Results <empty>' )

    self.cinp.call( '/api/v1/Processor/BuildJob:%s:(setResourceResults)' % self.job_id, { 'name': self.name, 'index': self.index, 'results': results } )

  def setScore( self, score ):
    if score is not None:
      logging.info( 'MCP: Score "%s"' % score )
    else:
      logging.info( 'MCP: Score <undefined>' )

    self.cinp.call( '/api/v1/Processor/BuildJob:%s:(setResourceScore)' % self.job_id, { 'name': self.name, 'index': self.index, 'score': score } )

  def uploadedPackages( self, package_files ):
    if not package_files:
      return

    self.cinp.call( '/api/v1/Processor/BuildJob:%s:(addPackageFiles)' % self.job_id, { 'name': self.name, 'index': self.index, 'package_files': package_files } )

  def getConfigStatus( self, resource, index=None, count=None ):
    logging.info( 'MCP: Config Status for "%s" index: "%s", count: "%s"' % ( resource, index, count ) )
    args = { 'name': resource }
    if index is not None:
      args[ 'index' ] = index

    if count is not None:
      args[ 'count' ] = count

    return self.cinp.call( '/api/v1/Processor/BuildJob:%s:(getConfigStatus)' % self.job_id, args )[ 'value' ]

  def getProvisioningInfo( self, resource, index=None, count=None ):
    logging.info( 'MCP: Provisioning Info for "%s" index: "%s", count: "%s"' % ( resource, index, count ) )
    args = { 'name': resource }
    if index is not None:
      args[ 'index' ] = index

    if count is not None:
      args[ 'count' ] = count

    return self.cinp.call( '/api/v1/Processor/BuildJob:%s:(getProvisioningInfo)' % self.job_id, args )[ 'value' ]

  def setConfigValues( self, values, resource, index=None, count=None ):
    logging.info( 'MCP: Setting Config Values "%s" index: "%s", count: "%s"' % ( resource, index, count ) )
    args = { 'name': resource }
    if index is not None:
      args[ 'index' ] = index

    if count is not None:
      args[ 'count' ] = count

    args[ 'values' ] = values

    return self.cinp.call( '/api/v1/Processor/BuildJob:%s:(setConfigValues)' % self.job_id, args )[ 'value' ]

  def getNetworkInfo( self, network ):
    logging.info( 'MCP: Network Info for "%s"' % network )
    args = { 'name': network }
    return self.cinp.call( '/api/v1/Processor/BuildJob:%s:(getNetworkInfo)' % self.job_id, args )[ 'value' ]
