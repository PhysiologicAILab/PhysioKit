from setuptools import setup, find_namespace_packages

# read the contents of your README file
from pathlib import Path
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(name='PhysioKit2',
      version='1.7.3',
      description="PhysioKit: An Open-Source, Low-Cost Physiological Computing Toolkit for Single- and Multi-User Studies",
      long_description=long_description,
      long_description_content_type='text/markdown',
      url='https://github.com/PhysiologicAILab/PhysioKit',
      author=['Jitesh Joshi', 'Katherine wang', 'Youngjun Cho'],
      author_email='youngjun.cho@ucl.ac.uk',
      license='MIT',
      install_requires=[
        'matplotlib',
        'neurokit2',
        'numpy',
        'opencv_contrib_python',
        'pyserial',
        'PySide6',
        'PySide6_Addons',
        'PySide6_Essentials',
        'scipy',
        'pandas',
        'torch',
        'setuptools'
      ],
      packages=find_namespace_packages(where="src"),
      package_dir={"": "src", 'analyze':"src/PhysioKit2/analysis_helper"},
      include_package_data=True,
      package_data={
          "PhysioKit2": ["*.txt"],
          "PhysioKit2": ["*.ui"],
          "PhysioKit2.images": ["*.png"],
          "PhysioKit2.sqa.ckpt": ["*.pth"],
          "PhysioKit2.sqa.config": ["*.json"],
          "PhysioKit2.analysis_helper.sample_data": ["*.txt"],
          "PhysioKit2.configs": ["*.json"],
          "PhysioKit2.configs.arm_due": ["*.json"],
          "PhysioKit2.configs.avr_default": ["*.json"],
      },
      exclude_package_data={"PhysioKit2": [".gitattributes"]},
      entry_points={
          'console_scripts': [
              'physiokit = PhysioKit2.main:main',
              'physiokit_analyze = PhysioKit2.analysis_helper.process_signals:main',
          ]
      }
      )