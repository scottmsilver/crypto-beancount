from setuptools import setup

setup(name='crypto-beancount',
      version='0.1',
      description='The funniest joke in the world',
      url='https://github.com/scottmsilver/crypto-beancount',
      author='Scott M. Silver',
      author_email='scottmsilver@gmail.com',
      license='MIT',
      packages=['app'],
      install_requires=[
          'ccxt',
          'python-dotenv',
          'simplejson'
      ],
      zip_safe=False)
