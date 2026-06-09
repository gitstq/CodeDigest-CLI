"""
CodeDigest-CLI 模块入口点。

支持通过 ``python -m codedigest`` 方式运行。
"""

from codedigest.cli import main
import sys

sys.exit(main())
