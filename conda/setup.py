from setuptools import setup, find_packages

setup(
    name='ELIXIR-IIB_IMPACT',
    version='0',
    url='/Users/giuseppedefazio/Documents/RTDA_UniBA/progetti/ELIXIR_citations',
    scripts=[
        '/Users/giuseppedefazio/Documents/RTDA_UniBA/progetti/ELIXIR_citations/ELIXIR.IT_IMPACT.py'],
    packages=['ELIXIR-IIB_IMPACT'],
    license='GNU GENERAL PUBLIC LICENSE',
    author='Defazio G.',
    author_email='giuseppe.defazio@uniba.it',
    description='''
    kMetaShot is a taxonomy classifier tool for 2nd and 3rd GS data for 
    shotgun metagenomics relying on an aligmnent free and k-mer/minimizer 
    based approach.
    '''
)