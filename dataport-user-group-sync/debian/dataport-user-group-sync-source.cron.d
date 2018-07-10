PATH=/bin:/sbin:/usr/bin:/usr/sbin
*/5 * * * * root univention-scp $(ucr get dataport/user_group_sync/source/destination/pwdfile) /var/lib/dataport-user-group-sync-source/* $(ucr get dataport/user_group_sync/source/destination/user)@$(ucr get dataport/user_group_sync/source/destination/address):/var/lib/dataport-user-group-sync-sink
