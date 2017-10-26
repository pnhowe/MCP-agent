import logging
import time
from threading import Thread

from cinp import client

PACKRAT_API_VERSION = 'v1.1'

class KeepAlive( Thread ):
  def __init__( self, cinp, *args, **kwargs ):
    super( KeepAlive, self ).__init__( *args, **kwargs )
    self.daemon = True
    self.cinp = cinp
    root = self.cinp.describe( '/api/v1/Repos' )[0]
    if root[ 'api-version' ] != PACKRAT_API_VERSION:
      raise Exception( 'Expected API version "%s" found "%s"' % ( PACKRAT_API_VERSION, root[ 'api-version' ] ) )

  def run( self ):
    while self.cinp:
      self.cinp.call( '/api/v1/Auth(keepalive)' )
      time.sleep( 60 )

class Packrat( object ):
  def __init__( self, host, proxy, name, psk ):
    self.name = name
    self.cinp = client.CInP( host, '/api/v1', proxy )
    self.token = self.cinp.call( '/api/v1/Auth(login)', { 'username': self.name, 'password': psk } )[ 'value' ]
    self.cinp.setAuth( name, self.token )
    self.keepalive = KeepAlive( self.cinp )
    self.keepalive.start()

  def logout( self ):
    self.keepalive.cinp = None
    self.cinp.call( '/api/v1/Auth(logout)', { 'token': self.token } )

  def _callback( self, pos, size ):
    logging.debug( 'Packrat: Uploading at %s of %s' % ( pos, size ) )

  def addPackageFile( self, file, justification, provenance, version=None ):
    logging.info( 'Packrat: Adding Packge File "%s"' % file.name )
    file_uri = self.cinp.uploadFile( '/api/FILES', file, self._callback )[ 'uri' ]
    logging.info( 'Packrat: Adding file "%s", justification: "%s", provenance: "%s", distro: "%s"' % ( file_uri, justification, provenance, version ) )
    result = self.cinp.call( '/api/v1/Repos/PackageFile(create)', { 'file': file_uri, 'justification': justification, 'provenance': provenance, 'version': version }, timeout=300 ) # it can sometimes take a while for packrat to commit large files
    return result[ 'value' ]

  def checkFileName( self, file_name ):
    result = self.cinp.call( '/api/v1/Repos/PackageFile(filenameInUse)', { 'file_name': file_name } )
    return result[ 'value' ]
