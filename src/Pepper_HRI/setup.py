import os

from setuptools import find_packages, setup


package_name = 'pepper_hri'


def package_files(directory):
    paths = []
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        files = [f for f in files if not f.endswith(('.pyc', '.pyo'))]
        if files:
            destination = os.path.join('share', package_name, root)
            paths.append((destination, [os.path.join(root, f) for f in files]))
    return paths


data_files = [
    ('share/ament_index/resource_index/packages', [os.path.join('resource', package_name)]),
    (os.path.join('share', package_name), ['package.xml']),
    (os.path.join('share', package_name, 'launch'), [
        'bootup.launch.py',
        'move_pepper.launch.py',
        'gesture_manager.launch.py',
        'pepper_real.launch.py',
        'pepper_sim.launch.py',
    ]),
]
data_files.extend(package_files('tablet_assets'))
data_files.extend(package_files('audio'))
data_files.extend(package_files('config'))

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(include=['audio', 'audio.*', 'gestures', 'gestures.*', 'tablet_assets', 'tablet_assets.*']),
    py_modules=['HRI_coordinator'],
    data_files=data_files,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='tom',
    maintainer_email='tom@example.com',
    description='Pepper HRI coordinator, tablet display, audio processing, and gesture nodes.',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'hri_coordinator = HRI_coordinator:main',
            'tablet_builder = tablet_assets.builder:main',
            'gesture_manager = gestures.gesture_manager:main',
            'audio_processor = audio.audio_processor_node:main',
            'gesture_manager_sim = gestures.gesture_manager_sim:main',
        ],
    },
)
