# Administrators

## Kubernetes Deployment

YAML files have been provided for deployment on Kubernetes in the `yaml` directory.

They are split by whether they pertain to the APEL REST interface, APEL Server or to the persistant MySQL database. These are then further divided into files for the service itself and the service's replication controller, which is responsible for keeping the service containers running.

There are, therefore, six YAML files.

* `yaml/accounting-mysql-rc.yaml`               - This configures the replication controller for the MySQL service
* `yaml/accounting-mysql-service.yaml`          - This is the MySQL service
* `yaml/accounting-server-rc.yaml`              - This configures the replication controller for the APEL Server service
* `yaml/accounting-server-service.yaml`         - This is the APEL server service
* `yaml/accounting-rest-interface-rc.yaml`      - This configures the replication controller for the APEL REST interface service
* `yaml/accounting-rest-interface-service.yaml` - This is the APEL REST interface service

## Exposed ports

80 - all traffic to this port is forwarded to port 443 by the Apache server.

443 - the Apache server forwards (HTTPS) traffic to the APEL REST interface, which returns a Django view for recognised URL patterns.

3306 - used by the APEL REST interface and APEL Server service to communitcate with the MySQL

## Interacting with Running Docker Containers on Kubernetes

To do this, you must first install `kubectl` (See [Setting up kubectl](https://coreos.com/kubernetes/docs/latest/configure-kubectl.html) for a guide how to do this)

1. List the "pods". You are looking for something of the form `accounting-server-rc-XXXXX` or `accounting-rest-interface-rc-XXXXX`

   `kubectl -s kubernetes_ip --user="kubectl" --token="auth_token" --insecure-skip-tls-verify=true get pods --namespace=kube-system`

   Note, you will need to replace `kubernetes_ip` and `auth_token` with there proper values.

2. Open a terminal running on the Indigo Datacloud APEL Accounting Server

   `kubectl -s kubernetes_ip --user="kubectl" --token="auth_token" --insecure-skip-tls-verify=true exec -it accounting-server-rc-XXXXX --namespace=kube-system bash`

   Note, you will need to replace `accounting-server-rc-XXXXX` with its true value.

You should now have terminal access to the Accounting Server.

## Services Running in the APEL REST Interface Container
* `httpd`: The Apache webserver hosting the REST interface
* `cron` : Necessary to periodically update IGTF Trust Bundle and CRLs

## Services Running in the APEL Server Container
* `apeldbloader-cloud` : Loads received messages into the MySQL imagedd
* `cron` : Necessary to periodically run the Summariser

## Important APEL Server Configuration files

* `/etc/init.d/apeldbloader-cloud` : Registers the cloud loader as a service

* `/etc/apel/cloudloader.cfg` : Configures the cloud loader

* `/etc/apel/cloudsummariser.cfg` : Configures the cloud summariser

## Important APEL REST Interface Configuration files

* `/etc/httpd/conf.d/apel_rest_api.conf` : Enforces HTTPS

* `/etc/httpd/conf.d/ssl.conf` : Handles the HTTPS

## Important APEL Server Scripts

* `/etc/cron.d/cloudsummariser` : Cron job that runs `run_cloud_summariser.sh`

* `/usr/bin/run_cloud_summariser.sh` : Stops the loader service, summarises the database and restarts the loader

## Register the service as a protected resource with the Indigo Identity Access Management (IAM)

1. On the [IAM homepage](https://iam-test.indigo-datacloud.eu/dashboard#/home):
   * click "MitreID Dashboard"
   * click "Self Service Protected Resource Registration"
   * click "New Resource".

2. On the "Main" tab, give this resource an appropriate Client Name.

3. Click Save.

4. Store the ClientID, Client Secret, and Registration Access Token; as the ID and Secret will need to be put into the appropriate yaml file later, and the token will be needed to make further modifications to this registration.

## Authorize new PaaS (Platform as a Service) Platform components to view Summaries

* In `yaml/accounting-rest-interface-rc.yaml`, add the IAM registered ID corresponding to the service in the env variable `ALLOWED_FOR_GET`. It should be of form below, quotes included. Python needs to be able to interpret this variable as a list of strings, the outer quotes prevent kubernetes interpreting it as something meaningful in YAML. The accounting-rest-interface-rc on kubernetes will have to be restarted for that to take effect. This can be done by deleting the accounting-rest-interface-service pod.

`"['XXXXXXXXXXXX','XXXXXXXXXXXXXXXX']".`

## How to update an already deployed service to 1.5.0 (from 1.4.0)
These instructions assume the containers were previously deployed with docker-compose and they use docker-compose to upgrade to the new version

1. Stop the APEL REST Interface container
```
docker-compose -f yaml/docker-compose.yaml stop apel_rest_interface
```

2. In `yaml/apel_rest_interface.env`, change
```
IAM_URL=https://example-iam.example.url.eu/introspect
```
to
```
IAM_URLS=[\'example-iam.example.url.eu\']
```

3. In `yaml/docker-compose.yaml`, change
```
indigodatacloud/accounting:1.4.0-1
```
to 
```
indigodatacloud/accounting:1.5.0-1
```

4. Now, start the APEL Rest Interface Container
```
docker-compose -f yaml/docker-compose.yaml up -d apel_rest_interface
```

## How to update an already deployed service to 1.4.0 (from 1.3.2)
This section assumes previous deployment via the `docker/run_container.sh` script.

1. Determine the Accounting container ID using `docker ps`. Expected output is below.

```
CONTAINER ID             IMAGE                                ...
<server_container_id>    indigodatacloud/accounting:1.3.2-1   ...
<database_container_id>  mysql:5.6                            ...
...                      ...                                  ...
```   

2. Run `docker exec -it <container_id>` to open an interactive shell from within the docker image.

3. Run `service httpd stop`

4. Ensure all messages have been loaded. I.e. `tail /var/log/cloud/loader.log` shows "INFO - Found 0 messages" as the last message

5. Run `service apeldbloader-cloud stop`

6. Comment out the summariser cron in `/etc/cron.d/cloudsummariser`

7. Ensure the summariser is not running. I.e. `tail /var/log/cloud/summariser.log`. The last lines in the log should be as below:
```
summariser - INFO - Summarising complete.
summariser - INFO - ========================================
```

8. Exit the container with the `exit` command

9. Stop and delete the Server and Database container.
```
docker stop <server_container_id> <database_container_id>
docker rm <server_container_id> <database_container_id>
```

10. Follow [README.md](../README.md#running-the-docker-image-on-centos-7-and-ubuntu-1604) to deploy version 1.4.0. You will need to use the same mysql passwords as in the previous deployment.

## How to update an already deployed service to 1.3.2 (from 1.2.1)
This section assumes deployment via the `docker/run_container.sh` script.

1. Determine the Accounting container ID using `docker ps`. Expected output is below.

```
CONTAINER ID             IMAGE                                ...
<server_container_id>    indigodatacloud/accounting:1.2.1-1   ...
<database_container_id>  mysql:5.6                            ...
...                      ...                                  ...
```   

2. Run `docker exec -it <container_id>` to open an interactive shell from within the docker image.

3. While in the container, download the [update_schema.sql](scripts/update_schema.sql).

4. Run `service httpd stop`

5. Ensure all messages have been loaded. I.e. `tail /var/log/cloud/loader.log` shows "INFO - Found 0 messages" as the last message

6. Run `service apeldbloader-cloud stop`

7. Comment out the summariser cron in `/etc/cron.d/cloudsummariser`

8. Ensure the summariser is not running. I.e. `tail /var/log/cloud/summariser.log`. The last lines in the log should be as below:

```
summariser - INFO - Summarising complete.
summariser - INFO - ========================================
```

9. Exit the container with the `exit` command

10. From the host, make a database dump. This is necessary to preserve data.

```
mysqldump -h 0.0.0.0 -u root -p apel_rest > apel_rest.sql
```

11. Stop and Delete all the Server and Database container.

```
docker stop <server_container_id> <database_container_id>
docker rm <server_container_id> <database_container_id>
```

12. Re-launch the database container with

```
docker run -v /var/lib/mysql:/var/lib/mysql --name apel-mysql -v `pwd`/docker/etc/mysql/conf.d:/etc/mysql/conf.d -p 3306:3306 -e "MYSQL_ROOT_PASSWORD=****" -e "MYSQL_DATABASE=apel_rest" -e "MYSQL_USER=apel" -e "MYSQL_PASSWORD=****" -d mysql:5.6
```

13. Load the database dump.

```
mysql -h 0.0.0.0 -u root -p apel_rest < apel_rest.sql
```

14. Apply the `update_schema.sql` to upgrade the schema to support Cloud Usage Record v0.4. 

```
mysql -h 0.0.0.0 -u root -p apel_rest < scripts/update_schema.sql
```

15. Launch tne new version of the APEL REST container. You may wish to edit this command to mount a certificate.

```
docker run -d --link apel-mysql:mysql -p 80:80 -p 443:443 -v /var/spool/apel/cloud:/var/spool/apel/cloud -e "MYSQL_PASSWORD=****" -e "ALLOWED_FOR_GET=****" -e "SERVER_IAM_ID=****" -e "SERVER_IAM_SECRET=****" -e "DJANGO_SECRET_KEY=****" indigodatacloud/accounting:X.X.X-X
```

16. Confirm the new container is up and running by going to `https://\<hostname\>/api/v1/cloud/record/summary/`

## How to update an already deployed service to 1.2.1 (from <1.2.1)
1. Run `docker exec -it apel_server_container_id bash` to open an interactive shell from within the docker image.

2. Disable the summariser cron job, `/etc/cron.d/cloudsummariser`, and if running, wait for the summariser to stop.

3. Stop the apache server with `service httpd stop`.

4. Ensure all messages have been loaded, i.e. `/var/spool/apel/cloud/incoming/` contains no unloaded messages.

5. Because this update does not alter any interactions between the container and other services/components/containers, the old Accounting container can now simply be deleted and the new version launched in it's place.
