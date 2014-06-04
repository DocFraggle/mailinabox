# Creates DNS zone files for all of the domains of all of the mail users
# and mail aliases and restarts nsd.
########################################################################

import os, os.path, urllib.parse, time, re

from mailconfig import get_mail_domains

def do_dns_update(env):
	# What domains should we serve DNS for?
	domains = set()

	# Ensure the PUBLIC_HOSTNAME is in that list.
	domains.add(env['PUBLIC_HOSTNAME'])

	# Add all domain names in use by email users and mail aliases.
	domains |= get_mail_domains(env)
	
	# Make a nice and safe filename for each domain.
	zonefiles = []
	for domain in domains:
		zonefiles.append((domain, urllib.parse.quote(domain, safe='') + ".txt" ))

	# Write zone files.
	os.makedirs('/etc/nsd/zones', exist_ok=True)
	updated_domains = []
	for domain, zonefile in zonefiles:
		records = build_zone(domain, env)
		if write_nsd_zone(domain, "/etc/nsd/zones/" + zonefile, records, env):
			updated_domains.append(domain)

	# Write the main nsd.conf file.
	write_nsd_conf(zonefiles)

	# Write the OpenDKIM configuration tables.
	write_opendkim_tables(zonefiles, env)

	# Kick nsd.
	os.system("service nsd restart")

	# Kick opendkim.
	os.system("service opendkim restart")

	if len(updated_domains) == 0: updated_domains = ['(no domains required an update)']
	return "Updated: " + ",".join(updated_domains) + "\n"

########################################################################

def build_zone(domain, env):
	records = []
	records.append((None,  "NS",  "ns1.%s." % env["PUBLIC_HOSTNAME"]))
	records.append((None,  "NS",  "ns2.%s." % env["PUBLIC_HOSTNAME"]))
	records.append((None,  "A",   env["PUBLIC_IP"]))
	records.append((None,  "MX",  "10 %s." % env["PUBLIC_HOSTNAME"]))
	records.append((None,  "TXT", '"v=spf1 mx -all"'))
	records.append(("www", "A",   env["PUBLIC_IP"]))

	# In PUBLIC_HOSTNAME, also define ns1 and ns2.
	if domain == env["PUBLIC_HOSTNAME"]:
		records.append(("ns1", "A",   env["PUBLIC_IP"]))
		records.append(("ns2", "A",   env["PUBLIC_IP"]))

	# If OpenDKIM is in use..
	opendkim_record_file = os.path.join(env['STORAGE_ROOT'], 'mail/dkim/mail.txt')
	if os.path.exists(opendkim_record_file):
		# Append the DKIM TXT record to the zone as generated by OpenDKIM, after string formatting above.
		with open(opendkim_record_file) as orf:
			m = re.match(r"(\S+)\s+IN\s+TXT\s+(\(.*\))\s*;", orf.read(), re.S)
			records.append((m.group(1), "TXT", m.group(2)))

		# Append ADSP (RFC 5617) and DMARC records.
		records.append(("_adsp._domainkey", "TXT", '"dkim=all"'))
		records.append(("_dmarc", "TXT", '"v=DMARC1; p=quarantine"'))

	return records

########################################################################

def write_nsd_zone(domain, zonefile, records, env):
	# We set the administrative email address for every domain to domain_contact@[domain.com].
	# You should probably create an alias to your email address.

	zone = """
$ORIGIN {domain}.    ; default zone domain
$TTL 86400           ; default time to live

@ IN SOA ns1.{primary_domain}. hostmaster.{primary_domain}. (
           __SERIAL__     ; serial number
           28800       ; Refresh
           7200        ; Retry
           864000      ; Expire
           86400       ; Min TTL
           )
"""

	# Replace replacement strings.
	zone = zone.format(domain=domain, primary_domain=env["PUBLIC_HOSTNAME"])

	# Add records.
	for subdomain, querytype, value in records:
		if subdomain:
			zone += subdomain
		zone += "\tIN\t" + querytype + "\t"
		zone += value + "\n"

	# Set the serial number.
	serial = time.strftime("%Y%m%d00")
	if os.path.exists(zonefile):
		# If the zone already exists, is different, and has a later serial number,
		# increment the number.
		with open(zonefile) as f:
			existing_zone = f.read()
			m = re.search(r"(\d+)\s*;\s*serial number", existing_zone)
			if m:
				existing_serial = m.group(1)
				existing_zone = existing_zone.replace(m.group(0), "__SERIAL__     ; serial number")

				# If the existing zone is the same as the new zone (modulo the serial number),
				# there is no need to update the file.
				if zone == existing_zone:
					return False

				# If the existing serial is not less than the new one, increment it.
				if existing_serial >= serial:
					serial = str(int(existing_serial) + 1)

	zone = zone.replace("__SERIAL__", serial)

	# Write the zone file.
	with open(zonefile, "w") as f:
		f.write(zone)

	return True # file is updated

########################################################################

def write_nsd_conf(zonefiles):
	with open("/etc/nsd/nsd.conf", "w") as f:
		f.write("""
server:
  hide-version: yes

  # identify the server (CH TXT ID.SERVER entry).
  identity: ""

  # The directory for zonefile: files.
  zonesdir: "/etc/nsd/zones"
  
# ZONES
""")

		for domain, zonefile in zonefiles:
			f.write("""
zone:
	name: %s
	zonefile: %s
""" % (domain, zonefile))

########################################################################

def write_opendkim_tables(zonefiles, env):
	# Append a record to OpenDKIM's KeyTable and SigningTable for each domain.
	#
	# The SigningTable maps email addresses to signing information. The KeyTable
	# maps specify the hostname, the selector, and the path to the private key.
	#
	# DKIM ADSP and DMARC both only support policies where the signing domain matches
	# the From address, so the KeyTable must specify that the signing domain for a
	# sender matches the sender's domain.
	#
	# In SigningTable, we map every email address to a key record named after the domain.
	# Then we specify for the key record its domain, selector, and key.

	opendkim_key_file = os.path.join(env['STORAGE_ROOT'], 'mail/dkim/mail.private')
	if not os.path.exists(opendkim_key_file): return

	with open("/etc/opendkim/KeyTable", "w") as f:
		f.write("\n".join(
			"{domain} {domain}:mail:{key_file}".format(domain=domain, key_file=opendkim_key_file)
			for domain, zonefile in zonefiles
		))

	with open("/etc/opendkim/SigningTable", "w") as f:
		f.write("\n".join(
			"*@{domain} {domain}".format(domain=domain)
			for domain, zonefile in zonefiles
		))

