#!/usr/bin/env -S PYTHONPATH=../../../tools/extract-utils python3
#
# SPDX-FileCopyrightText: 2024 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path

from extract_utils.fixups_blob import (
    blob_fixup,
    blob_fixups_user_type,
)
from extract_utils.fixups_lib import (
    lib_fixups,
    lib_fixups_user_type,
)
from extract_utils.main import (
    ExtractUtils,
    ExtractUtilsModule,
)

namespace_imports = [
    'device/xiaomi/sm8150-common',
    'hardware/qcom-caf/sm8150',
    'hardware/qcom-caf/wlan',
    'hardware/xiaomi',
    'vendor/qcom/opensource/commonsys/display',
    'vendor/qcom/opensource/commonsys-intf/display',
    'vendor/qcom/opensource/dataservices',
    'vendor/qcom/opensource/display',
]

def lib_fixup_vendor_suffix(lib: str, partition: str, *args, **kwargs):
    return f'{lib}_{partition}' if partition == 'vendor' else None

lib_fixups: lib_fixups_user_type = {
    **lib_fixups,
    (
        'com.qualcomm.qti.dpm.api@1.0',
        'libmmosal',
        'vendor.qti.hardware.fm@1.0',
        'vendor.qti.imsrtpservice@3.0',
        'vendor.qti.hardware.wifidisplaysession@1.0',
    ): lib_fixup_vendor_suffix,
}

blob_fixups: blob_fixups_user_type = {
    'system_ext/lib64/libwfdnative.so': blob_fixup()
        .add_needed('libinput_shim.so'),
    'vendor/etc/init/init.mi_thermald.rc': blob_fixup()
        .regex_replace(' +seclabel u:r:mi_thermald:s0\n', ''),
    'vendor/lib64/libdpps.so': blob_fixup()
        .replace_needed('libtinyxml2.so', 'libtinyxml2-v34.so'),
    ('vendor/lib64/mediadrm/libwvdrmengine.so', 'vendor/lib64/libwvhidl.so'): blob_fixup()
        .add_needed('libcrypto_shim.so'),
    ('vendor/etc/seccomp_policy/atfwd@2.0.policy', 'vendor/etc/seccomp_policy/wfdhdcphalservice.policy'): blob_fixup()
        .add_line_if_missing('gettid: 1'),
    'vendor/etc/seccomp_policy/vendor.qti.hardware.dsp.policy': blob_fixup()
        .add_line_if_missing('madvise: 1'),
    'vendor/etc/wfdconfig.xml': blob_fixup()
        .regex_replace('<AudioStreamInSuspend>0</AudioStreamInSuspend>', '<AudioStreamInSuspend>1</AudioStreamInSuspend>')
        .regex_replace('<HID>0</HID>', '<HID>1</HID>'),
}  # fmt: skip

def configure_qtigef_makefiles(vendor_path):
    """Keep stock and nabu-patched GEF install rules mutually exclusive."""
    bp_path = Path(vendor_path) / 'Android.bp'
    marker = 'cc_prebuilt_library_shared {\n    name: "libqtigef",\n'
    enabled = (
        '    enabled: select(soong_config_variable("nabu_dolby", "replace_qtigef"), {\n'
        '        true: false,\n'
        '        default: true,\n'
        '    }),\n'
    )
    bp = bp_path.read_text()
    if bp.count(marker) != 1:
        raise ValueError('Expected exactly one shared libqtigef prebuilt')
    if marker + enabled not in bp:
        bp_path.write_text(bp.replace(marker, marker + enabled, 1))

    # Also preserve the product-package guard when vendor makefiles regenerate.
    mk_path = Path(vendor_path) / 'sm8150-common-vendor.mk'
    guard = (
        '# Dolby products install libqtigef_nabu at the same path instead.\n'
        'ifneq ($(TARGET_ENABLE_XIAOMI_DOLBY),true)\n'
        'PRODUCT_PACKAGES += libqtigef\n'
        'endif\n'
    )
    mk = mk_path.read_text()
    if guard not in mk:
        entry = '    libqtigef \\\n'
        if mk.count(entry) != 1:
            raise ValueError('Expected exactly one generated libqtigef product entry')
        mk_path.write_text(mk.replace(entry, '', 1).rstrip() + '\n\n' + guard)


class NabuAwareExtractUtilsModule(ExtractUtilsModule):
    def write_makefiles(self, legacy, extract_factory):
        super().write_makefiles(legacy, extract_factory)
        configure_qtigef_makefiles(self.vendor_path)


module = NabuAwareExtractUtilsModule(
    'sm8150-common',
    'xiaomi',
    blob_fixups=blob_fixups,
    lib_fixups=lib_fixups,
    namespace_imports=namespace_imports,
)

module.add_proprietary_file('proprietary-files-fm.txt').add_copy_files_guard(
    'TARGET_HAS_FM', 'true'
)

module.add_proprietary_file('proprietary-files-phone.txt').add_copy_files_guard(
    'TARGET_IS_TABLET', 'true', invert=True
)

if __name__ == '__main__':
    utils = ExtractUtils.device(module)
    utils.run()
