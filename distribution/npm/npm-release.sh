# Set NPM_TOKEN environment variable to the User's token before running the script
#
# USAGE: ./npm-release.sh
# Picks up the version from latest tag

VERSION=`git describe --abbrev=0 --tags`
VERSION="${VERSION:1:${#VERSION}}" # Remove starting 'v' v0.0.1 => 0.0.1
PACKAGE=./package.json
BACKUP=./package.json.bck

PKG_ROOT=`pwd`
NPM_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $NPM_DIR

# Add Readme to NPM package to show in NPM Package's webpage
cp $PKG_ROOT/README.md $NPM_DIR

# 1. Replace __VERSION__ from package.json with version tag passed as first argument
cp $PACKAGE $BACKUP
sed -i '' -e "s/__VERSION__/$VERSION/g" $PACKAGE

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
rm $NPM_DIR/README.md
echo "Successfully published NPM for version $VERSION"
exit 0
