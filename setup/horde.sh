#!/bin/bash
# Horde
##########################

source setup/functions.sh # load our functions
source /etc/mailinabox.conf # load global vars

# ### Installing Horde Groupware

echo "Installing Horde Groupware"

wget -O /tmp/mysql-apt-config_0.8.1-1_all.deb https://dev.mysql.com/get/mysql-apt-config_0.8.1-1_all.deb && \
dpkg -i /tmp/mysql-apt-config_0.8.1-1_all.deb && \
apt-get -y update && \
apt-get -y upgrade

apt_install \
        dbconfig-common \
        php5-cli php5-sqlite php5-gd php5-imap php5-curl php-pear php-apc curl libapr1 libtool libcurl4-openssl-dev php-xml-parser \
        php5 php5-dev php5-gd php5-fpm memcached php5-memcached mysql-server php5-mysql

if [ ! -d /opt/horde ]
then
	pear upgrade PEAR
	pear channel-discover pear.horde.org
	pear install horde/horde_role
	pear run-scripts horde/horde_role
	pear install -a -B horde/webmail
	pear install -a -B date
	pear install -a -B pear.horde.org/passwd
	pear install -a -B pear.horde.org/Horde_ActiveSync

	webmail_installer
fi


















#wget https://downloads.bitnami.com/files/stacks/horde/5.2.17-0/bitnami-horde-5.2.17-0-linux-x64-installer.run && \
#chmod u+x bitnami-horde-5.2.17-0-linux-x64-installer.run && \
#./bitnami-horde-5.2.17-0-linux-x64-installer.run

#/opt/horde/php/bin/pear install date
#/opt/horde/php/bin/pear install pear.horde.org/passwd
#/opt/horde/php/bin/pear install pear.horde.org/Horde_ActiveSync

#chgrp daemon -R /opt/horde/apps/horde/htdocs/
#for i in `find /opt/horde/apps/horde/htdocs -type d -name config`; do chmod g+rwX -R $i; done
#chgrp daemon /home/user-data/mail/users.sqlite
#chmod g+rwX /home/user-data/mail/users.sqlite

#echo "echo \"Starting Horde\"" > /etc/rc.local
#echo "/opt/horde/ctlscript.sh start" >> /etc/rc.local

