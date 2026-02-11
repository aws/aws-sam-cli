"""
Instrument SAM CLI source files with debug logging for layer ordering investigation.
This script patches layer_downloader.py, lambda_image.py, and tar.py to emit
DEBUG_LAYER_ORDER log lines that help diagnose non-deterministic layer ordering.
"""

import sys


def patch_file(filepath, replacements):
    with open(filepath, "r") as f:
        content = f.read()

    for old, new in replacements:
        if old not in content:
            print(f"WARNING: Could not find patch target in {filepath}:")
            print(f"  Looking for: {old[:80]}...")
            sys.exit(1)
        content = content.replace(old, new)

    with open(filepath, "w") as f:
        f.write(content)
    print(f"Patched {filepath}")


# --- Patch layer_downloader.py ---
patch_file("samcli/local/layers/layer_downloader.py", [
    (
        # Add debug logging to download_all
        '        layer_dirs = []\n'
        '        for layer in layers:\n'
        '            layer_dirs.append(self.download(layer, force))\n'
        '\n'
        '        return layer_dirs',

        '        LOG.warning("DEBUG_LAYER_ORDER: download_all called with %d layers", len(layers))\n'
        '        for i, layer in enumerate(layers):\n'
        '            LOG.warning("DEBUG_LAYER_ORDER: input layer[%d] arn=%s name=%s", i, layer.arn, layer.name)\n'
        '\n'
        '        layer_dirs = []\n'
        '        for layer in layers:\n'
        '            layer_dirs.append(self.download(layer, force))\n'
        '\n'
        '        LOG.warning("DEBUG_LAYER_ORDER: download_all returning %d layers", len(layer_dirs))\n'
        '        for i, layer in enumerate(layer_dirs):\n'
        '            LOG.warning("DEBUG_LAYER_ORDER: output layer[%d] name=%s codeuri=%s", i, layer.name, layer.codeuri)\n'
        '\n'
        '        return layer_dirs'
    ),
])

# --- Patch lambda_image.py ---
patch_file("samcli/local/docker/lambda_image.py", [
    (
        # Add debug logging to _generate_dockerfile
        '        for layer in layers:\n'
        '            dockerfile_content = dockerfile_content + f"ADD {layer.name} {LambdaImage._LAYERS_DIR}\\n"\n'
        '        return dockerfile_content',

        '        for layer in layers:\n'
        '            dockerfile_content = dockerfile_content + f"ADD {layer.name} {LambdaImage._LAYERS_DIR}\\n"\n'
        '        LOG.warning("DEBUG_LAYER_ORDER: Generated Dockerfile:\\n%s", dockerfile_content)\n'
        '        return dockerfile_content'
    ),
    (
        # Add debug logging to _build_image tar_paths
        '            for layer in layers:\n'
        '                tar_paths[layer.codeuri] = "/" + layer.name\n'
        '\n'
        '            # Use shared tar filter for Windows compatibility',

        '            for layer in layers:\n'
        '                tar_paths[layer.codeuri] = "/" + layer.name\n'
        '                LOG.warning("DEBUG_LAYER_ORDER: tar_paths entry: %s -> /%s", layer.codeuri, layer.name)\n'
        '\n'
        '            LOG.warning("DEBUG_LAYER_ORDER: tar_paths keys order: %s", list(tar_paths.keys()))\n'
        '            LOG.warning("DEBUG_LAYER_ORDER: tar_paths values order: %s", list(tar_paths.values()))\n'
        '\n'
        '            # Use shared tar filter for Windows compatibility'
    ),
    (
        # Add debug logging to build method decision
        '        if (\n'
        '            self.force_image_build\n'
        '            or image_not_found\n'
        '            or any(layer.is_defined_within_template for layer in downloaded_layers)\n'
        '            or not runtime\n'
        '        ):',

        '        LOG.warning(\n'
        '            "DEBUG_LAYER_ORDER: Build decision - force=%s image_not_found=%s"\n'
        '            " any_template_layers=%s runtime=%s rapid_image=%s",\n'
        '            self.force_image_build, image_not_found,\n'
        '            any(layer.is_defined_within_template for layer in downloaded_layers),\n'
        '            runtime, rapid_image)\n'
        '        if (\n'
        '            self.force_image_build\n'
        '            or image_not_found\n'
        '            or any(layer.is_defined_within_template for layer in downloaded_layers)\n'
        '            or not runtime\n'
        '        ):'
    ),
])

# --- Patch tar.py ---
patch_file("samcli/lib/utils/tar.py", [
    (
        '    with tarfile.open(fileobj=tarballfile, mode=mode, dereference=do_dereferece) as archive:\n'
        '        for path_on_system, path_in_tarball in tar_paths.items():\n'
        '            archive.add(path_on_system, arcname=path_in_tarball, filter=tar_filter)',

        '    with tarfile.open(fileobj=tarballfile, mode=mode, dereference=do_dereferece) as archive:\n'
        '        for path_on_system, path_in_tarball in tar_paths.items():\n'
        '            LOG.warning("DEBUG_LAYER_ORDER: Adding to tarball: %s -> %s", path_on_system, path_in_tarball)\n'
        '            archive.add(path_on_system, arcname=path_in_tarball, filter=tar_filter)'
    ),
])

print("All files instrumented successfully.")
