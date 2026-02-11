"""
Instrument SAM CLI source files with debug logging for layer ordering investigation.
This script patches layer_downloader.py, lambda_image.py, and tar.py to emit
DEBUG_LAYER_ORDER log lines that help diagnose non-deterministic layer ordering.
"""

import sys


def patch_file(filepath, replacements):
    with open(filepath, "r") as f:
        content = f.read()

    for i, (old, new) in enumerate(replacements):
        if old not in content:
            print(f"FAIL: Could not find patch target #{i} in {filepath}")
            # Show first 120 chars of what we're looking for
            print(f"  Looking for: {old[:120]!r}...")
            # Try to find partial match
            first_line = old.split("\n")[0].strip()
            if first_line in content:
                idx = content.index(first_line)
                print(f"  First line found at char {idx}, context:")
                print(repr(content[idx:idx+300]))
            else:
                print(f"  First line not found: {first_line!r}")
            sys.exit(1)
        content = content.replace(old, new, 1)

    with open(filepath, "w") as f:
        f.write(content)
    print(f"Patched {filepath} ({len(replacements)} patches)")


# =============================================================================
# Patch 1: samcli/local/layers/layer_downloader.py
# =============================================================================
patch_file("samcli/local/layers/layer_downloader.py", [
    # 1a: Add debug logging to download_all
    (
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
    # 1b: Add debug logging to download method - cache check and download path
    (
        '        layer_path = Path(self.layer_cache).resolve().joinpath(layer.name)\n'
        '        is_layer_downloaded = self._is_layer_cached(layer_path)\n'
        '        layer.codeuri = str(layer_path)\n'
        '\n'
        '        if is_layer_downloaded and not force:\n'
        '            LOG.info("%s is already cached. Skipping download", layer.arn)\n'
        '            return layer',

        '        layer_path = Path(self.layer_cache).resolve().joinpath(layer.name)\n'
        '        is_layer_downloaded = self._is_layer_cached(layer_path)\n'
        '        layer.codeuri = str(layer_path)\n'
        '        LOG.warning("DEBUG_LAYER_ORDER: download() layer=%s path=%s cached=%s force=%s",\n'
        '            layer.name, layer_path, is_layer_downloaded, force)\n'
        '\n'
        '        if is_layer_downloaded and not force:\n'
        '            LOG.warning("DEBUG_LAYER_ORDER: SKIPPING download for %s (cached)", layer.arn)\n'
        '            return layer'
    ),
    # 1c: Add debug logging after successful download with content verification
    (
        '                unzip_from_uri(\n'
        '                    layer_zip_uri,\n'
        '                    layer_zip_path,\n'
        '                    unzip_output_dir=layer.codeuri,\n'
        '                    progressbar_label="Downloading {}".format(layer.layer_arn),\n'
        '                )\n'
        '\n'
        '                download_lock.release_lock(success=True)\n'
        '                return layer',

        '                unzip_from_uri(\n'
        '                    layer_zip_uri,\n'
        '                    layer_zip_path,\n'
        '                    unzip_output_dir=layer.codeuri,\n'
        '                    progressbar_label="Downloading {}".format(layer.layer_arn),\n'
        '                )\n'
        '\n'
        '                # Debug: verify extracted content\n'
        '                import os as _os\n'
        '                for _root, _dirs, _files in _os.walk(layer.codeuri):\n'
        '                    for _f in _files:\n'
        '                        _fpath = _os.path.join(_root, _f)\n'
        '                        if _f.endswith(".py"):\n'
        '                            try:\n'
        '                                with open(_fpath) as _fh:\n'
        '                                    LOG.warning("DEBUG_LAYER_ORDER: extracted %s content: %s",\n'
        '                                        _fpath, _fh.read().strip())\n'
        '                            except Exception:\n'
        '                                pass\n'
        '\n'
        '                download_lock.release_lock(success=True)\n'
        '                return layer'
    ),
])

# =============================================================================
# Patch 2: samcli/local/docker/lambda_image.py
# =============================================================================
patch_file("samcli/local/docker/lambda_image.py", [
    # 2a: Add debug logging to _generate_dockerfile
    (
        '        for layer in layers:\n'
        '            dockerfile_content = dockerfile_content + f"ADD {layer.name} {LambdaImage._LAYERS_DIR}\\n"\n'
        '        return dockerfile_content',

        '        for layer in layers:\n'
        '            dockerfile_content = dockerfile_content + f"ADD {layer.name} {LambdaImage._LAYERS_DIR}\\n"\n'
        '        LOG.warning("DEBUG_LAYER_ORDER: Generated Dockerfile:\\n%s", dockerfile_content)\n'
        '        return dockerfile_content'
    ),
    # 2b: Add debug logging to _build_image tar_paths
    (
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
    # 2c: Add debug logging to build method decision
    (
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
    # 2d: Log Docker build stream output to capture cache hits (Using -> CACHED)
    (
        '                            # Process stream messages\n'
        '                            if "stream" in log:\n'
        '                                stream_msg = log["stream"].strip()\n'
        '                                if stream_msg:\n'
        '                                    LOG.debug(f"Build stream: {stream_msg}")',

        '                            # Process stream messages\n'
        '                            if "stream" in log:\n'
        '                                stream_msg = log["stream"].strip()\n'
        '                                if stream_msg:\n'
        '                                    LOG.warning("DEBUG_LAYER_ORDER: Build stream: %s", stream_msg)\n'
        '                                    LOG.debug(f"Build stream: {stream_msg}")'
    ),
])

# =============================================================================
# Patch 3: samcli/lib/utils/tar.py
# =============================================================================
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

print("\nAll files instrumented successfully.")
