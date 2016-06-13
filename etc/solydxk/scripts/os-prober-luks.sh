#/bin/sh

if [ -e /etc/solydxk/scripts/os-prober-luks.txt ] && [ -e /usr/bin/os-prober ]; then
	if ! grep -q "cryptsetup" /usr/bin/os-prober; then
		sed -i -e '/partitions.*(.*).*{/r /etc/solydxk/scripts/os-prober-luks.txt' /usr/bin/os-prober
	fi 
fi
