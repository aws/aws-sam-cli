$src_code=$args[0]
$build_path=$args[1]
$output_name=$args[2]
$resource_type=$args[3]

Write-Host "Building $resource_type $src_code into $build_path"
# pwd

$temp_path="$build_path\tmp_building\output"
if ( $resource_type -eq "Layer" ){
    $temp_path="$build_path\tmp_building\output\python"
    Write-Host "new path $temp_path"
}

if (Test-Path $build_path) {
    Write-Host "$build_path exists. Skip create."
}
else {
    Write-Host "Creating $build_path"
    mkdir $build_path
}

Remove-Item -Recurse -Force "$build_path\*"
mkdir "$build_path\tmp_building" -ErrorAction 0 | Out-Null
mkdir "$build_path\tmp_building\output" -ErrorAction 0 | Out-Null
mkdir $temp_path -ErrorAction 0 | Out-Null

# ls $build_path
Copy-Item -Recurse "$src_code\*" $temp_path

pip install -r "$temp_path\requirements.txt" -t "$temp_path\." | Out-Null

Add-Type -assembly "system.io.compression.filesystem"
[io.compression.zipfile]::CreateFromDirectory("$build_path\tmp_building\output", "$build_path\$output_name")

Remove-Item -Recurse -Force "$build_path\tmp_building"

Write-Host "Build done!"