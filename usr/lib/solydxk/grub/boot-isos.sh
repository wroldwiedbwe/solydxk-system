#! /bin/bash

# boot-isos.sh  - 2015-07-09

ISODIR='/boot-isos'

function check_partition {
	DSK=$1		# Partition (e.g. /dev/sda1)
	UUID=$2		# UUID of this partition
	MNT=$3		# Current mount point or empty if not mounted

	# Get the third character of the partition
	CHR=${DSK:7:1}
	# Get the last characters of the partition
	PRT=${DSK:8}

	# Mount the partition if it is not mounted already
	if [ ! "$MNT" ]; then
		MNT="/mnt/$CHR$PRT"
		#echo "Mount $DSK on $MNT"
		mkdir -p $MNT
		mount $DSK $MNT
	fi

	# SolydXK - add live iso menu entries if isos were found in given partition
	ISOPATH="$MNT$ISODIR"
	#echo "Check for isos in $ISOPATH"
	if [ "$(ls -A $ISOPATH/*.iso 2>/dev/null)" ]; then
		# Get the partition scheme (mbr or gpt)
		PTS=$(parted -m ${DSK:0:8} print | grep -F ${DSK:0:8} | cut -d: -f6)
		# Get boot parameters
		BOOTPRMS=""
		if [ -f /etc/default/grub ]; then
			. /etc/default/grub
			BOOTPRMS="$GRUB_CMDLINE_LINUX_DEFAULT"
		fi
		# Add an empty line
		cat <<-EOT
		 	menuentry ' ' {
		 		true
		 	}
		EOT
		# Loop through the ISOs
		for ISO in $ISOPATH/*.iso; do
			ISONAME=$(basename $ISO)
			cat <<-EOT
			 	menuentry 'Live: $ISONAME' {
			 		insmod part_$PTS
			 		insmod loopback
			 		search --no-floppy --fs-uuid --set=isopart $UUID
			 		loopback loop (\$isopart)$ISODIR/$ISONAME
			 		linux (loop)/live/vmlinuz boot=live findiso=$ISODIR/$ISONAME noprompt noeject noswap config $BOOTPRMS
			 		initrd (loop)/live/initrd.img
			 	}
			EOT
		done
	fi

	# Unmount the device if it was mounted by this script
	if [ ! "$3" ]; then
		umount $MNT 2>/dev/null
		rmdir $MNT
	fi
}

# Search for isos on all available partitions
while read -r BLK; do
	NM=$(echo $BLK | awk '{print $1}')
	TP=$(echo $BLK | awk '{print $2}')
	FS=$(echo $BLK | awk '{print $3}')
	ID=$(echo $BLK | awk '{print $4}')
	MP=$(echo $BLK | awk '{print $5}')
	# only look at partitions with a file system (i.e. ignore extended and
	# unformatted (BIOS boot) partitions) which are not root or swap (can't use
	# MP for that, as that might miss swap partitions on other disks)
	if [ $FS ] && [ $FS != swap ] && [ "$TP" == "part" ] && [ "$MP" != "/" ]; then
		check_partition "$NM" "$ID" "$MP"
	fi
done < <(lsblk -lpno NAME,TYPE,FSTYPE,UUID,MOUNTPOINT)	# will only work for root!
