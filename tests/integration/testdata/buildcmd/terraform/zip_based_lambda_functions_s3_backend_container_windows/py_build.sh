#!/bin/sh
src_code=$1
build_path=$2
output_name=$3
resource_type=$4
echo "building ${resource_type} ${src_code} into ${build_path}"

temp_path=${build_path}/tmp_building/${output_name}
if [[ "${resource_type}" == "Layer" ]]; then
  temp_path=${build_path}/tmp_building/${output_name}/python
  echo "new path ${temp_path}"
fi

mkdir -p ${build_path}
mkdir -p ${build_path}/tmp_building
mkdir -p ${build_path}/tmp_building/${output_name}
mkdir -p ${temp_path}
rm -rf ${temp_path}/*

cp -r $src_code/* ${temp_path}
pip install -r ${temp_path}/requirements.txt -t ${temp_path}/.
current=$(pwd)
cd ${build_path}/tmp_building/${output_name}
zip -r ${output_name} .
cd ${current}
mv "${build_path}/tmp_building/${output_name}/${output_name}" "${build_path}/$output_name"
rm -rf ${build_path}/tmp_building/${output_name}
rm -rf ${build_path}/tmp_building
