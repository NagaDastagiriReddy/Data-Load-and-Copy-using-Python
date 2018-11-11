# MIT License
#
# Copyright (c) 2018 Capital One Services, LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import pytest
import mock
import pg8000, psycopg2

from locopy import Base
from locopy.utility import get_redshift_yaml
from locopy.errors import ConnectionError, DisconnectionError, DBError


GOOD_CONFIG_YAML = """
host: host
port: 1234
database: database
user: id
password: pass
other: stuff
extra_conn:
    extra: 123
    another: 321"""

DBAPIS = [pg8000, psycopg2]


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_base_constructor(credentials, dbapi):
    b = Base(dbapi=dbapi, **credentials)
    assert b.host == "host"
    assert b.port == "port"
    assert b.database == "database"
    assert b.user == "user"
    assert b.password == "password"


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_base_constructor_with_extras(credentials, dbapi):
    credentials["extra"] = 123
    credentials["another"] = 321
    b = Base(dbapi=dbapi, **credentials)
    assert b.host == "host"
    assert b.port == "port"
    assert b.database == "database"
    assert b.user == "user"
    assert b.password == "password"
    assert b.extra_conn == {"extra": 123, "another": 321}


@pytest.mark.parametrize("dbapi", DBAPIS)
@mock.patch("locopy.utility.open", mock.mock_open(read_data=GOOD_CONFIG_YAML))
def test_base_constructor_yaml(dbapi):
    b = Base(dbapi=dbapi, config_yaml="some_config.yml")
    assert b.host == "host"
    assert b.port == 1234
    assert b.database == "database"
    assert b.user == "id"
    assert b.password == "pass"
    assert b.other == "stuff"
    assert b.extra_conn == {"extra": 123, "another": 321}


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_is_connected(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        b = Base(dbapi=dbapi, **credentials)
        assert b._is_connected() is False

    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        b = Base(dbapi=dbapi, **credentials)
        b._connect()
        assert b._is_connected() is True

    # throws exception in _is_connected
    b = Base(dbapi=dbapi, **credentials)
    del b.conn
    assert b._is_connected() is False


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_connect(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        b = Base(dbapi=dbapi, **credentials)
        b._connect()
        mock_connect.assert_called_with(
            host="host", user="user", port="port", password="password", database="database"
        )

    credentials["extra"] = 123
    credentials["another"] = 321
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        b = Base(dbapi=dbapi, **credentials)
        b._connect()
        mock_connect.assert_called_with(
            host="host",
            user="user",
            port="port",
            password="password",
            database="database",
            extra=123,
            another=321,
        )

    # side effect exception
    mock_connect.side_effect = Exception("Connect Exception")
    with pytest.raises(ConnectionError):
        b._connect()


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_disconnect(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        b = Base(dbapi=dbapi, **credentials)
        b._connect()
        b._disconnect()
        b.conn.close.assert_called_with()
        b.cursor.close.assert_called_with()

    # side effect exception
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        b._connect()
        b.conn.close.side_effect = Exception("Disconnect Exception")
        with pytest.raises(DisconnectionError):
            b._disconnect()


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_disconnect_no_conn(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        b = Base(dbapi=dbapi, **credentials)
        b._disconnect()


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_execute(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        with Base(dbapi=dbapi, **credentials) as test:
            print(test)
            test.execute("SELECT * FROM some_table")
            assert test.cursor.execute.called is True


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_execute_no_connection_exception(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        test = Base(dbapi=dbapi, **credentials)
        test.conn = None
        test.cursor = None
        with pytest.raises(ConnectionError):
            test.execute("SELECT * FROM some_table")


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_execute_sql_exception(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        with Base(dbapi=dbapi, **credentials) as test:
            test.cursor.execute.side_effect = Exception("SQL Exception")
            with pytest.raises(DBError):
                test.execute("SELECT * FROM some_table")


@pytest.mark.parametrize("dbapi", DBAPIS)
@mock.patch("pandas.DataFrame")
def test_to_dataframe_all(mock_pandas, credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        mock_connect.return_value.cursor.return_value.fetchall.return_value = [(1, 2), (2, 3), (3,)]
        with Base(dbapi=dbapi, **credentials) as test:
            test.execute("SELECT 'hello world' AS fld")
            df = test.to_dataframe()

    assert mock_connect.return_value.cursor.return_value.fetchall.called
    mock_pandas.assert_called_with(test.cursor.fetchall(), columns=[])


@pytest.mark.parametrize("dbapi", DBAPIS)
@mock.patch("pandas.DataFrame")
def test_to_dataframe_custom_size(mock_pandas, credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        mock_connect.return_value.cursor.return_value.fetchmany.return_value = [
            (1, 2),
            (2, 3),
            (3,),
        ]
        with Base(dbapi=dbapi, **credentials) as test:
            test.execute("SELECT 'hello world' AS fld")
            df = test.to_dataframe(size=5)

    mock_connect.return_value.cursor.return_value.fetchmany.assert_called_with(5)
    mock_pandas.assert_called_with(test.cursor.fetchmany(), columns=[])


@pytest.mark.parametrize("dbapi", DBAPIS)
@mock.patch("pandas.DataFrame")
def test_to_dataframe_none(mock_pandas, credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        mock_connect.return_value.cursor.return_value.fetchmany.return_value = []
        with Base(dbapi=dbapi, **credentials) as test:
            test.execute("SELECT 'hello world' WHERE 1=0")
            assert test.to_dataframe(size=5) is None
            mock_pandas.assert_not_called()


@pytest.mark.parametrize("dbapi", DBAPIS)
def test_get_column_names(credentials, dbapi):
    with mock.patch(dbapi.__name__ + ".connect") as mock_connect:
        mock_connect.return_value.cursor.return_value.description = [["COL1"], ["COL2"]]
        with Base(dbapi=dbapi, **credentials) as test:
            assert test.column_names() == ["col1", "col2"]

        mock_connect.return_value.cursor.return_value.description = [("COL1",), ("COL2",)]
        with Base(dbapi=dbapi, **credentials) as test:
            assert test.column_names() == ["col1", "col2"]

        mock_connect.return_value.cursor.return_value.description = (("COL1",), ("COL2",))
        with Base(dbapi=dbapi, **credentials) as test:
            assert test.column_names() == ["col1", "col2"]
