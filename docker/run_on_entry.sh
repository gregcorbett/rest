#!/bin/bash

# install IGTF trust bundle 10 minutes after start up
echo "yum -y update ca-policy-egi-core >> /var/log/IGTF-startup-update.log" | at now + 10 min

if [ -z $MYSQL_PORT_3306_TCP_ADDR ]
then
    $MYSQL_PORT_3306_TCP_ADDR = $MYSQL_HOST
fi

echo "[client]
user=apel
password=$MYSQL_PASSWORD
host=$MYSQL_PORT_3306_TCP_ADDR" >> /etc/my.cnf

# add clouddb.cfg, so that the default user of mysql is APEL
echo "[db]
# type of database
backend = mysql
# host with database
hostname = 10.254.10.21
# port to connect to
port = 3306
# database name
name = apel_rest
# database user
username = apel
# password for database
password = $MYSQL_PASSWORD
# how many records should be put/fetched to/from database
# in single query
records = 1000
# option for summariser so that SummariseVMs is called
type = cloud" >> /etc/apel/clouddb.cfg

echo "
ALLOWED_FOR_GET=$ALLOWED_FOR_GET
SERVER_IAM_ID=$SERVER_IAM_ID
SERVER_IAM_SECRET=$SERVER_IAM_SECRET

" >> /var/www/html/apel_rest/settings.py

sed -i "s/Put a secret here/$DJANGO_SECRET_KEY/g" /var/www/html/apel_rest/settings.py

# start apache
service httpd start

#start cron
service crond start

# start the loader service
service apeldbloader-cloud start

# Make cloud spool dir owned by apache
chown apache -R /var/spool/apel/cloud/

#keep docker running
while true
do
  sleep 1
done
