import logging
from urllib import request

from cinp import client


class PasswordManager:
  def __init__( self, username, password ):
    self.username = username
    self.password = password

  def find_user_password( self, realm, authuri ):
    return self.username, self.password


class Confluence( client.CInP ):  # we are going to cheet and barrow the proxy setup from the cinp client.  Code reuse FTW!
  def __init__( self, host, proxy, username, password, verify_ssl=True ):
    super.__init__( host, '/', proxy, verify_ssl  )

    pwd_manager = PasswordManager( username, password )
    self.opener.add_handler( request.HTTPBasicAuthHandler( pwd_manager ) )

  def upload( self, local_filepath, page ):
    logging.debug( 'confluence: attaching "{0}" to page "{1}"'.format( local_filepath, page ) )
    header_map = {}
    header_map[ 'X-Atlassian-Token' ] = 'no-check'

    uri = 'confluence/rest/api/content/{0}/child/attachment'.format( page )

    data = open( local_filepath, 'rb' )

    ( http_code, data, header_map ) = self._request( 'UPLOAD', uri, data, header_map=header_map )

    if http_code != 200:
      raise Exception( 'Unexpected response code "{0}" when adding attachment'.format( http_code ) )

    logging.info( 'confluence: added attachment "{0}" id:"{1}" to page "{2}"'.format( local_filepath, data[ 'id' ], page ) )


# https://developer.atlassian.com/confdev/confluence-server-rest-api/confluence-rest-api-examples
