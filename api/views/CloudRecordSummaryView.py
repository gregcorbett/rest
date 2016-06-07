import base64
import ConfigParser
import datetime
import httplib
import json
import logging
import MySQLdb
import os
import urllib2

from dirq.queue import Queue, QueueError
from rest_framework.pagination import PaginationSerializer
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from rest_framework.response import Response
from rest_framework.views import APIView


class CloudRecordSummaryView(APIView):
    """
    Retrieve Cloud Accounting Summaries.

    .../cloud/record/summary?Group=<group_name>&from=<date_from>&to=<date_to>

    Will return the summary for group_name at all services,
    between date_from and date_to as daily summaries

    .../cloud/record/summary?service=<service_name>&from=<date_from>&to=<date_to>

    Will return the summary for service_name at all groups,
    between date_from and date_to as daily summaries

    .../cloud/record/summary?from=<date_from>
    Will give summary for whole infrastructure from <data> to now
    """

    def get(self, request, format=None):
        """
        Retrieve Cloud Accounting Summaries.

        .../cloud/record/summary?Group=<group_name>&from=<date_from>&to=<date_to>

        Will return the summary for group_name at all services,
        between date_from and date_to as daily summaries

        .../cloud/record/summary?service=<service_name>&from=<date_from>&to=<date_to>

        Will return the summary for service_name at all groups,
        between date_from and date_to as daily summaries

        .../cloud/record/summary?from=<date_from>
        Will give summary for whole infrastructure from <data> to now
        """
        logger = logging.getLogger(__name__)

        try:
            client_token = self._request_to_token(request)
        except KeyError:
            logger.error("No AUTHORIZATION header provided, authentication failed.")
            return Response(status=401)
        except IndexError:
            logger.error("AUTHORIZATION header provided, but not of expected form.")
            logger.error(request.META['HTTP_AUTHORIZATION'])
            return Response(status=401)

        logger.info("%s Authenticated", client_token)

        try:
            client_id = self._token_to_id(client_token)
        except urllib2.HTTPError, e:
            logger.error('HTTPError = ' + str(e.code))
            logger.error('Could not Authorize.')
            return Response(status=401)
        except urllib2.URLError, e:
            logger.error('URLError = ' + str(e.reason))
            logger.error('Could not Authorize.')
            return Response(status=401)
        except httplib.HTTPException:
            logger.error('HTTPException')
            logger.error('Could not Authorize.')
            return Response(status=401)
        except KeyError:
            logger.error("No client id in IAM response, likely token has expired")
            return Response(status=401)        

        logger.debug("Token identifed as %s", client_id)

        if not self._is_client_authorized(client_id):
            logger.error("%s does not have permission to view summaries", client_id)
            return Response(status=403)

        logger.info("%s Authorized.", client_id)
 
        # parse query parameters
        (group_name,
         service_name,
         start_date,
         end_date) = self._parse_query_parameters(request)

        if start_date is None:
            # querying without a from is not supported
            return Response(status=501)

        # Read configuration from file
        try:
            dbcp = ConfigParser.ConfigParser()
            dbcp.read(settings.CLOUD_DB_CONF)

            db_hostname = dbcp.get('db', 'hostname')
            # db_port = int(dbcp.get('db', 'port'))
            db_name = dbcp.get('db', 'name')
            db_username = dbcp.get('db', 'username')
            db_password = dbcp.get('db', 'password')
        except (ConfigParser.Error, ValueError, IOError) as err:
            logger.warning('Error in configuration file %s: %s',
                           settings.CLOUD_DB_CONF,
                           str(err))
            logger.warning('Using default configuration.')

            db_hostname = 'localhost'
            db_name = 'apel_rest'
            db_username = 'root'
            db_password = ''

        # get the data requested
        try:
            database = MySQLdb.connect(db_hostname,
                                       db_username,
                                       db_password,
                                       db_name)
        except MySQLdb.OperationalError:
            logger.error("Could not connect to %s at %s using %s, %s",
                         db_name, db_hostname, db_username, db_password)
            return Response(status=500)

        cursor = database.cursor()

        if group_name is not None:
            cursor.execute('select * from VCloudSummaries where VOGroup = %s and EarliestStartTime > %s and LatestStartTime < %s',
                           [group_name, start_date, end_date])

        elif service_name is not None:
            cursor.execute('select * from VCloudSummaries where SiteName = %s and EarliestStartTime > %s and LatestStartTime < %s',
                           [service_name, start_date, end_date])

        else:
            cursor.execute('select * from VCloudSummaries where EarliestStartTime > %s',
                           [start_date])

        results = self._filter_cursor(cursor)
        results = self._paginate_result(request, results)
        return Response(results, status=200)

###############################################################################
#                                                                             #
# Helper methods                                                              #
#                                                                             #
###############################################################################

    def _parse_query_parameters(self, request):
        """Parse expected query parameters from the given HTTP request."""
        group_name = request.GET.get('group', '')
        if group_name is "":
            group_name = None

        service_name = request.GET.get('service', '')
        if service_name is "":
            service_name = None

        start_date = request.GET.get('from', '')
        if start_date is "":
            start_date = None

        end_date = request.GET.get('to', '')
        if end_date is "":
            end_date = datetime.datetime.now()

        return (group_name, service_name, start_date, end_date)

    def _paginate_result(self, request, result):
        """Paginate result based on the request and apel_rest settings."""
        paginator = Paginator(result, settings.RESULTS_PER_PAGE)
        try:
            page = request.GET.get('page')
        except AttributeError:
            page = 1

        try:
            result = paginator.page(page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            result = paginator.page(1)
        except EmptyPage:
            # If page is out of range (e.g. 9999),
            # deliver last page of results.
            result = paginator.page(paginator.num_pages)

        # context allows for clickable REST Framework links
        serializer = PaginationSerializer(instance=result,
                                          context={'request': request})
        return serializer.data

    def _filter_cursor(self, cursor):
        """Filter database results based on setting.RETURN_HEADERS."""
        columns = cursor.description
        results = []
        for value in cursor.fetchall():
            result = {}
            for index, column in enumerate(value):
                header = columns[index][0]
                if header in settings.RETURN_HEADERS:
                    result.update({header: column})
            results.append(result)

        return results

    def _request_to_token(self, request):
        #get the token
        try:
            token = request.META['HTTP_AUTHORIZATION'].split()[1]
        except (KeyError, IndexError) as e:
            raise e
        return token

    def _token_to_id(self, token):
        try:
            auth_request = urllib2.Request('https://iam-test.indigo-datacloud.eu/introspect',
                                       data='token=%s' % token)

            server_id = settings.SERVER_IAM_ID
            server_secret = settings.SERVER_IAM_SECRET

            base64string = base64.encodestring('%s:%s' % (server_id, server_secret)).replace('\n', '')
            auth_request.add_header("Authorization", "Basic %s" % base64string)
            auth_result = urllib2.urlopen(auth_request)

            auth_json = json.loads(auth_result.read())
            client_id = auth_json['client_id']
        except (urllib2.HTTPError,
                urllib2.URLError,
                httplib.HTTPException,
                KeyError) as e:
            raise e

        return client_id

    def _is_client_authorized(self, client_id):
        return client_id in settings.ALLOWED_FOR_GET