PATH=/bin:/sbin:/usr/bin:/usr/sbin
*/5 * * * * root univention-scp $(ucr get dataport/user_group_sync/sink/source/pwdfile) $(ucr get dataport/user_group_sync/sink/source/user)@$(ucr get dataport/user_group_sync/sink/source/address):/var/lib/dataport-user-group-sync-source/$(ucr get dataport/user_group_sync/sink/identifier)/* /var/lib/dataport-user-group-sync-sink && user_group_sync_sink.py
