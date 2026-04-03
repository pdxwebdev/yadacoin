sed -i.bak "1s/.*/$1/" VERSION && rm VERSION.bak
git commit VERSION -m "feat: inc version, v$1"
git tag -a v$1 -m "$2"
git push origin master --tags $3
