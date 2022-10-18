$src_code=$args[0]
$build_path=$args[1]
$output_name=$args[2]

Write-Host "Building $src_code into $build_path"
# pwd

if (Test-Path $build_path) {
    Write-Host "$build_path exists. Skip create."
}
else {
    Write-Host "Creating $build_path"
    mkdir $build_path
}

Remove-Item -Recurse -Force $build_path\*

mkdir $build_path\tmp_building -ErrorAction 0 | Out-Null

# ls $build_path
Copy-Item -Recurse $src_code\* $build_path\tmp_building

pip install -r $build_path\tmp_building\requirements.txt -t $build_path\tmp_building\. | Out-Null

Add-Type -assembly "system.io.compression.filesystem"
[io.compression.zipfile]::CreateFromDirectory("$build_path\tmp_building", "$build_path\$output_name")

Remove-Item -Recurse -Force $build_path\tmp_building

Write-Host "Build done!"