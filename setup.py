from setuptools import setup

setup(name='crypto-beancount',
      version='0.1',
      description='Convert your crypto account into a ledger via beancount.',
      url='https://github.com/scottmsilver/crypto-beancount',
      author='Scott M. Silver',
      author_email='scottmsilver@gmail.com',
      license='MIT',
      packages=['app'],
      install_requires=[
          'ccxt',
          'python-dotenv',
          'simplejson',
          'python-dateutil'
      ],
      zip_safe=False)
