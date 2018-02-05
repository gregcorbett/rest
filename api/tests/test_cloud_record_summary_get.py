"""This module tests GET requests to the Cloud Sumamry Record endpoint."""

import logging
import MySQLdb
import os
import tempfile
from api.utils.TokenChecker import TokenChecker
from django.core.urlresolvers import reverse
from django.test import Client, TestCase
from mock import patch

QPATH_TEST = '/tmp/django-test/'

# A test database config to use instead of the default,
# to prevent unit tests running in the default database.
DB_CONF = """[db]
# type of database
backend = mysql
# host with database
hostname = localhost
# port to connect to
port = 3306
# database name
name = test_apel_rest
# database user
username = root
# password for database
password =
# how many records should be put/fetched to/from database
# in single query
records = 1000
# option for summariser so that SummariseVMs is called
type = cloud"""


class CloudRecordSummaryGetTest(TestCase):
    """Tests GET requests to the Cloud Sumamry Record endpoint."""

    def setUp(self):
        """Prevent logging from appearing in test output."""
        logging.disable(logging.CRITICAL)

    @patch.object(TokenChecker, 'valid_token_to_id')
    def test_cloud_record_summary_get_IAM_fail(self, mock_valid_token_to_id):
        """
        Test what happens if we fail to contact the IAM.

        i.e, _token_to_id returns None

        IAM = Identity and Access Management
        """
        # Mock the functionality of the IAM
        # Used in the underlying GET method
        # Simulates a failure to translate a token to an ID
        mock_valid_token_to_id.return_value = None

        with self.settings(ALLOWED_FOR_GET='TestService'):
            # Make (and check) the GET request
            self._check_summary_get(401,
                                    options=("?group=TestGroup"
                                             "&from=20000101&to=20191231"),
                                    authZ_header_cont="Bearer TestToken")

    @patch.object(TokenChecker, 'valid_token_to_id')
    def test_cloud_record_summary_get_400(self, mock_valid_token_to_id):
        """Test a GET request without the from field."""
        # Mock the functionality of the IAM
        # Simulates the translation of a token to an ID
        # Used in the underlying GET method
        mock_valid_token_to_id.return_value = 'TestService'

        with self.settings(ALLOWED_FOR_GET='TestService'):
            # Make (and check) the GET request
            self._check_summary_get(400, options="?group=TestGroup",
                                    authZ_header_cont="Bearer TestToken")

    @patch.object(TokenChecker, 'valid_token_to_id')
    def test_cloud_record_summary_get_403(self, mock_valid_token_to_id):
        """Test an unauthorized service cannot make a GET request."""
        # Mock the functionality of the IAM
        # Simulates the translation of a token to an unauthorized ID
        # Used in the underlying GET method
        mock_valid_token_to_id.return_value = 'FakeService'

        with self.settings(ALLOWED_FOR_GET='TestService'):
            # Make (and check) the GET request
            self._check_summary_get(403,
                                    options=("?group=TestGroup"
                                             "&from=20000101&to=20191231"),
                                    authZ_header_cont="Bearer TestToken")

    def test_cloud_record_summary_get_401(self):
        """Test an unauthenticated GET request."""
        # Test without the HTTP_AUTHORIZATION header
        # Make (and check) the GET request
        self._check_summary_get(401,
                                options=("?group=TestGroup"
                                         "&from=20000101&to=20191231"))

        # Test with a malformed HTTP_AUTHORIZATION header
        # Make (and check) the GET request
        self._check_summary_get(401,
                                options=("?group=TestGroup"
                                         "&from=20000101&to=20191231"),
                                authZ_header_cont="TestToken")

    @patch.object(TokenChecker, 'valid_token_to_id')
    def test_cloud_record_summary_get_200(self, mock_valid_token_to_id):
        """Test a successful GET request."""
        # Connect to database
        database = self._connect_to_database()
        # Clean up any lingering example data.
        self._clear_database(database)
        # Add example data
        self._populate_database(database)

        # Create an empty database config file
        tmp_dir = tempfile.mkdtemp(prefix='tmp')
        db_cfg_file, db_cfg_path = tempfile.mkstemp(prefix='db',
                                                    dir=tmp_dir)

        # Populate the empty database config with the test databse config
        os.write(db_cfg_file, DB_CONF)
        os.close(db_cfg_file)

        # Mock the functionality of the IAM
        mock_valid_token_to_id.return_value = 'TestService'

        expected_response = ('{'
                             '"count":2,'
                             '"next":null,'
                             '"previous":null,'
                             '"results":[{'
                             '"WallDuration":86399,'
                             '"Year":2016,'
                             '"Day":30,'
                             '"Month":7'
                             '},{'
                             '"WallDuration":43200,'
                             '"Year":2016,'
                             '"Day":31,'
                             '"Month":7}]}')

        with self.settings(ALLOWED_FOR_GET='TestService',
                           CLOUD_DB_CONF=db_cfg_path,
                           RETURN_HEADERS=["WallDuration",
                                           "Day",
                                           "Month",
                                           "Year"]):
            try:
                self._check_summary_get(200,
                                        expected_response=expected_response,
                                        options=("?group=TestGroup"
                                                 "&from=20000101&to=20191231"),
                                        authZ_header_cont="Bearer TestToken")
            finally:
                # Clean up after test.
                os.remove(db_cfg_path)
                self._clear_database(database)
                database.close()

    def tearDown(self):
        """Delete any messages under QPATH and re-enable logging.INFO."""
        logging.disable(logging.NOTSET)

    def _check_summary_get(self, expected_status, expected_response=None,
                           options='', authZ_header_cont=None):
        """Helper method to make a GET request."""
        test_client = Client()
        # Form the URL to make the GET request to
        url = ''.join((reverse('CloudRecordSummaryView'), options))

        if authZ_header_cont is not None:
            # If content for a HTTP_AUTHORIZATION has been provided,
            # make the GET request with the appropriate header
            response = test_client.get(url,
                                       HTTP_AUTHORIZATION=authZ_header_cont)
        else:
            # Otherise, make a GET request without a HTTP_AUTHORIZATION header
            response = test_client.get(url)

        # Check the expected response code has been received.
        self.assertEqual(response.status_code, expected_status)

        if expected_response is not None:
            # Check the response received is as expected.
            self.assertEqual(response.content, expected_response)

    def _populate_database(self, database):
        """Populate the database with example summaries."""
        cursor = database.cursor()

        # Insert example usage data
        cursor.execute('INSERT INTO CloudRecords '
                       '(VMUUID, SiteID, GlobalUserNameID, VOID, '
                       'VOGroupID, VORoleID, Status, StartTime, '
                       'SuspendDuration, WallDuration, PublisherDNID, '
                       'CloudType, ImageId, '
                       'CloudComputeServiceID) '
                       'VALUES '
                       '("TEST-VM", 1, 1, 1, 1, 1, "Running", '
                       '"2016-07-30 00:00:00", 0, 86399, 1, "TEST", "1", '
                       '1);')

        # Insert example usage data
        cursor.execute('INSERT INTO CloudRecords '
                       '(VMUUID, SiteID, GlobalUserNameID, VOID, '
                       'VOGroupID, VORoleID, Status, StartTime, '
                       'SuspendDuration, WallDuration, PublisherDNID, '
                       'CloudType, ImageId, '
                       'CloudComputeServiceID) '
                       'VALUES '
                       '("TEST-VM", 1, 1, 1, 1, 1, "Running", '
                       '"2016-07-30 00:00:00", 0, 129599, 1, "TEST", "1", '
                       '1);')

        # These INSERT statements are needed
        # because we query VCloudSummaries
        cursor.execute('INSERT INTO Sites VALUES (1, "TestSite");')
        cursor.execute('INSERT INTO VOs VALUES (1, "TestVO");')
        cursor.execute('INSERT INTO VOGroups VALUES (1, "TestGroup");')
        cursor.execute('INSERT INTO VORoles VALUES (1, "TestRole");')
        cursor.execute('INSERT INTO DNs VALUES (1, "TestDN");')
        cursor.execute('INSERT INTO CloudComputeServices '
                       'VALUES (1, "TestService");')

        # Summarise example usage data
        cursor.execute('CALL SummariseVMs();')
        database.commit()

    def _clear_database(self, database):
        """Clear the database of example data."""
        cursor = database.cursor()

        cursor.execute('DELETE FROM CloudRecords '
                       'WHERE VMUUID="TEST-VM";')

        cursor.execute('DELETE FROM CloudSummaries '
                       'WHERE CloudType="TEST";')

        cursor.execute('DELETE FROM Sites '
                       'WHERE id=1;')

        cursor.execute('DELETE FROM VOs '
                       'WHERE id=1;')

        cursor.execute('DELETE FROM VOGroups '
                       'WHERE id=1;')

        cursor.execute('DELETE FROM VORoles '
                       'WHERE id=1;')

        cursor.execute('DELETE FROM DNs '
                       'WHERE id=1;')

        cursor.execute('DELETE FROM CloudComputeServices '
                       'WHERE id=1;')

        database.commit()

    def _connect_to_database(self,
                             host='localhost',
                             user='root',
                             password='',
                             name='test_apel_rest'):
        """Connect to and return a cursor to the given database."""
        database = MySQLdb.connect(host, user, password, name)
        return database
