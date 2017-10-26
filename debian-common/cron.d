PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

*/1 * * * * root [ -x /usr/sbin/nullunitIterate ] && /usr/sbin/nullunitIterate
