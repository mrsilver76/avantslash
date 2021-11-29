### If this script is renamed to "autoupgrade.sh", it can be called 
### from avantify.cgi .
###
### Before enabling the autoupdate feature, please consider
### protecting your installation against unauthorized use.
### Your site's URL may show up as an HTTP referrer on other sites.
### See authenticate/ directory for examples for use with Apache.
###
### This script will be called using /bin/sh. Do not use bash-specific
### constructs.

bailout () {
    echo "$@"
    echo "Aborted."
    exit 1
}

[ $# = 0 ] &&  bailout "Error: call as $0 <version>."

VERSION="$1"

tfname="__test$$"
touch $tfname 2>&1 || bailout "No write permission for directory" `pwd`
rm -f $tfname

tarfname="avantslash-$VERSION.tar.gz"

date=`date +%Y%m%d_%H%M`
bakfn=avantslash-backup-$date.tar.gz

# prevent "file '.' changed as we read it" error in GNU tar version <= 1.23
touch $bakfn 
tar czf $bakfn --exclude='*gz' . 2>&1 ||
    bailout "Error while making backup."

echo "Stored backup as $bakfn"

which wget > /dev/null ||
    bailout "Error: wget executable not available."

echo "Executing wget..."
wget -O "$tarfname" -U "Avantslash-autoupdate" \
    "http://avantslash.org/tarballs/$tarfname" 2>&1 ||
    bailout "Error executing wget"

# note: tarballs unpack to present directory
tar xzf $tarfname 2>&1 || bailout "Error while unpacking $tarfname."
echo "Unpacked $tarfname."

rm -f cache/* || bailout "Error while cleaning cache."
echo "Cleared cache."

echo "---AVANTSLASH UPGRADED SUCCESSFULLY TO VERSION $VERSION---"

exit 0


