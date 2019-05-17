import os
import logging
import time
from threading import Thread

from cinp import client

PACKRAT_API_VERSION = '2.0'


class KeepAlive( Thread ):
  def __init__( self, cinp, *args, **kwargs ):
    super( KeepAlive, self ).__init__( *args, **kwargs )
    self.daemon = True
    self.cinp = cinp

  def run( self ):
    while self.cinp:
      self.cinp.call( '/api/v2/User/Session(keepalive)' )
      time.sleep( 60 )


class Packrat( object ):
  def __init__( self, host, proxy, name, password ):
    self.name = name
    self.cinp = client.CInP( host, '/api/v2/', proxy )

    root = self.cinp.describe( '/api/v2/' )
    if root[ 'api-version' ] != PACKRAT_API_VERSION:
      raise Exception( 'Expected API version "{0}" found "{1}"'.format( PACKRAT_API_VERSION, root[ 'api-version' ] ) )

    self.token = self.cinp.call( '/api/v2/Auth/User(login)', { 'username': self.name, 'password': password } )
    self.cinp.setAuth( name, self.token )
    # self.keepalive = KeepAlive( self.cinp )
    # self.keepalive.start()

  def logout( self ):
    # self.keepalive.cinp = None
    self.cinp.call( '/api/v2/Auth/User(logout)', { 'token': self.token } )

  def _callback( self, pos, size ):
    logging.debug( 'Packrat: Uploading at {0} of {1}'.format( pos, size ) )

  def addPackageFile( self, file, justification, provenance, distroversion, type ):
    logging.info( 'Packrat: Adding Packge File "{0}"'.format( file.name ) )
    file_uri = self.cinp.uploadFile( '/api/upload', file, os.path.basename( file.name ), self._callback )
    distroversion_list = self.cinp.call( '/api/v2/Package/PackageFile(distroversionOptions)', { 'file': file_uri } )
    if distroversion is not None:
      if distroversion not in distroversion_list:
        raise Exception( 'distroversion "{0}" not in aviable distroverison list "{1}"'.format( distroversion, distroversion_list ) )
    else:
      if len( distroversion_list ) != 1:
        raise Exception( 'Unable to auto-detect distroversion, options: "{0}"'.format( distroversion_list ) )
      else:
        distroversion = distroversion_list[0]

    logging.info( 'Packrat: Adding file "{0}", justification: "{1}", provenance: "{2}", '
                  'distroversion: "{3}", type: "{4}"'.format( file_uri, justification, provenance, distroversion, type ) )

    result = self.cinp.call( '/api/v2/Package/PackageFile(create)',
                             {
                                 'file': file_uri,
                                 'justification': justification,
                                 'provenance': provenance,
                                 'distroversion': distroversion,
                                 'type': type
                             }, timeout=300 )  # it can sometimes take a while for packrat to commit large files, thus the long timeout
    return result

  def checkFileName( self, file_name ):
    result = self.cinp.call( '/api/v2/Package/PackageFile(filenameInUse)', { 'file_name': file_name } )
    return result
