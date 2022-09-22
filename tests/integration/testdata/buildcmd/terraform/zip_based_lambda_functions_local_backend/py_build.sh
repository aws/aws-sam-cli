src_code=$1
build_path=$2
output_name=$3
echo "building ${src_code} into ${build_path}"
pwd
mkdir -p ${build_path}
rm -rf ${build_path}/*
mkdir -p ${build_path}/tmp_building
tree ./
cp -r $src_code/* ${build_path}/tmp_building
pip install -r ${build_path}/tmp_building/requirements.txt -t ${build_path}/tmp_building/.
pushd ${build_path}/tmp_building/ && zip -r $output_name . && popd
mv "${build_path}/tmp_building/${output_name}" "${build_path}/$output_name"
rm -rf ${build_path}/tmp_building
pwd
tree ./