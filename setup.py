from setuptools import setup, find_packages


setup(
    name='ELIXIR-IIB_IMPACT',
    version='0',
    url='/Users/giuseppedefazio/Documents/RTDA_UniBA/progetti/ELIXIR_citations',
    scripts=[
        '/Users/giuseppedefazio/Documents/RTDA_UniBA/progetti/ELIXIR_citations/ELIXIR.IT_IMPACT.py'],
    #install_requires=['pyalex', 'pybliometics'],
    py_modules=[],
    license='GNU GENERAL PUBLIC LICENSE',
    author='Defazio G.',
    author_email='giuseppe.defazio@uniba.it',
    description='''
    CITATION OVERVIEW SYSTEM FOR BIBLIOMETRIC ASSESSMENT RELYING ON OPENALEX AND SCOPUS.
    POWERED BY ELIXIR-IIB.
    '''
)