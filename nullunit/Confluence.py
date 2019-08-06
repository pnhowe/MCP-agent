import logging
import socket
import json
from urllib3 import encode_multipart_formdata
from urllib import request

from cinp import client


class PasswordManager:
  def __init__( self, username, password ):
    self.username = username
    self.password = password

  def find_user_password( self, realm, authuri ):
    return self.username, self.password

  def add_password( self, *args, **kwargs ):
    pass


class Confluence( client.CInP ):  # we are going to cheet and barrow the proxy setup from the cinp client.  Code reuse FTW!
  def __init__( self, host, proxy, username, password, verify_ssl=True ):
    super().__init__( host, '/', proxy, verify_ssl  )

    pwd_manager = PasswordManager( username, password )
    self.opener.add_handler( request.HTTPBasicAuthHandler( pwd_manager ) )

  def upload( self, local_filepath, page, comment ):
    logging.debug( 'confluence: attaching "{0}" to page "{1}"'.format( local_filepath, page ) )
    timeout = 30
    header_map = {}
    header_map[ 'X-Atlassian-Token' ] = 'no-check'

    url = '{0}/rest/api/content/{1}/child/attachment'.format( self.host, page )

    file_reader = open( local_filepath, 'rb' )
    fields = { 'file': file_reader.read(), 'comment': 'Uploaded by MCP ' }
    file_reader.close()
    content, content_type = encode_multipart_formdata( fields )
    header_map[ 'Content-type' ] = content_type

    req = request.Request( url, data=content, headers=header_map, method='POST' )
    try:
      resp = self.opener.open( req, timeout=timeout )

    except request.HTTPError as e:
      raise client.ResponseError( 'HTTPError "{0}"'.format( e ) )

    except request.URLError as e:
      if isinstance( e.reason, socket.timeout ):
        raise client.Timeout( 'Request Timeout after {0} seconds'.format( timeout ) )

      raise client.ResponseError( 'URLError "{0}" for "{1}" via "{2}"'.format( e, url, self.proxy ) )

    except socket.timeout:
      raise client.Timeout( 'Request Timeout after {0} seconds'.format( timeout ) )

    except socket.error as e:
      raise client.ResponseError( 'Socket Error "{0}"'.format( e ) )

    if resp.code != 200:
      raise Exception( 'Unexpected response code "{0}" when adding attachment'.format( resp.code ) )

    data = json.loads( str( resp.read(), 'utf-8' ) )

    logging.info( 'confluence: added attachment "{0}" id:"{1}" to page "{2}"'.format( local_filepath, data[ 'id' ], page ) )


# https://developer.atlassian.com/confdev/confluence-server-rest-api/confluence-rest-api-examples
