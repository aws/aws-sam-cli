# Set NPM_TOKEN environment variable to the User's token before running the script
#
# USAGE: ./npm-release.sh <version of release>
# Example: ./npm-release.sh 0.0.1

VERSION=$1
PACKAGE=./package.json
BACKUP=./package.json.bck

# 1. Replace __VERSION__ from package.json with version tag passed as first argument
cp $PACKAGE $BACKUP
sed -i -e "s/__VERSION__/$VERSION/g" $PACKAGE

# Make sure the replace actually happened
grep __VERSION__ $PACKAGE
if [ $? -eq 0 ]
then
    echo "Replacing __VERSION__ in $PACKAGE was unsuccessful"
    cat $PACKAGE
    exit 1
fi

# 2. Generated package.json should be published to NPM
npm publish ./

if [ $? -ne 0 ]
then
    echo "ERROR publishing to npm"
    exit 1
fi

# Restore package.json file
mv $BACKUP $PACKAGE
echo "Successfully published NPM for version $VERSION"
exit 0
