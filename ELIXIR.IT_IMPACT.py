#!/usr/env/bin python3
__author__ = "Giuseppe Defazio"
__version__ = "1.0"


import os.path
import sys
from datetime import datetime as dt
import pybliometrics.scopus
from pybliometrics.scopus import CitationOverview
from functools import reduce
import pandas as pd
import numpy as np
import argcomplete
import argparse
import requests
import pyalex
import json
import re

def input_options():
    parser = argparse.ArgumentParser(
        description="This script interrogates OpenAlex and Scopus Api to obtain bibliometric features of papers related to ELIXIR IT services",
        prefix_chars="-")
    parser.add_argument("-i", "--input_excel", type=str,
                        help="The path to the input excel. An excel format example is provided in the GitHub page",
                        action="store", required=True)
                        # default='./Table S1-SAB-160224_lst.xlsx'
    parser.add_argument("-o", "--output_directory", type=str,
                        help="output directory", action="store", required=False,
                        default="./ELIXIR-IIB_impact")
    parser.add_argument("-a", "--openalex_key", type=str,
                        help="the OpenAlex API key to query",
                        action="store", required=True)
    parser.add_argument("-p", "--pybliometrics_key", type=str,
                        help="the Pybliometrics API key to query",
                        action="store", required=True)

    argcomplete.autocomplete(parser)
    return parser.parse_args()


class OpenAlexDoi:

    def __init__(self, service, plaftorm,  doi) -> None:
        self.service = service
        self.plaftorm = plaftorm
        self.doi = doi
        self.object = pyalex.Works()[f"https://doi.org/{doi}"]
        self.citations = self.object['cited_by_count']
        self.authors = pd.DataFrame(self.object['authorships'])
        self.cit_by_years = pd.DataFrame(self.object['counts_by_year'])
        # self.auth2orcid = pd.DataFrame(list(self.authors['author']))[['display_name','orcid']]

    def get_institutions(self) -> pd.DataFrame:
        melt_info = list()
        for i in range(0, self.authors.shape[0]):
            if self.authors.loc[i, 'raw_affiliation_strings'].__len__() != 0:
                try:
                    melt_info.append((self.authors.loc[i, 'institutions'][-1]['display_name'],
                                      self.authors.loc[i, 'institutions'][-1]['country_code']))
                except IndexError:
                    pass
                # df = pd.DataFrame(
                #     self.authors.loc[i, 'institutions'])[[
                #     'display_name', 'country_code', 'type']]
                # # df.loc[:,'author'] = self.authors.loc[i, 'raw_author_name']
                # melt_info.append(df)
        melt_info = set(melt_info)
        # try:
        #     melt = pd.concat(melt_info, axis=0, ignore_index=True, sort=False)
        #     melt.drop_duplicates()
        melt = pd.DataFrame(melt_info, columns=['institution', 'country'])
        melt['weigh'] = self.citations
        melt['service'] = self.service
        melt['plaftorm'] = self.plaftorm
        melt['doi'] = self.doi
            # melt.reset_index(inplace=True, drop=True)
        return melt
        # except Exception as e:
        #     print(e)

    def get_citing_works(self) -> tuple:
        if self.citations <= 200:
            ans = requests.get(self.object['cited_by_api_url'])
            j_ans = json.loads(ans.text.encode('utf-8'))
            #try:
            df = pd.DataFrame(j_ans['results'])
            if df.shape[0] == 0:
                return None, None
            else:
                # authorship contiene le info sugli autori dei lavori che citano i lavori
                # di elixiri
                c = 0
                citing_institutions = pd.DataFrame()
                # print(df)
                for i in df.index:
                    el = df.loc[i, 'authorships']
                    doiOfIter = df.loc[i, 'doi']
                    for dict_outhor in el:
                        citing_institutions.loc[c, 'service'] = self.service
                        citing_institutions.loc[c, 'platform'] = self.plaftorm
                        citing_institutions.loc[c, 'doi'] = self.doi
                        citing_institutions.loc[c, 'doiOfCiting'] = doiOfIter
                        # citing_institutions.loc[c, 'author'] = dict_outhor['author']['display_name']
                        if len(dict_outhor['institutions']) == 0:
                            citing_institutions.loc[c, 'institution'] = np.NAN
                            citing_institutions.loc[c, 'country'] = np.NAN
                        else:
                            citing_institutions.loc[c, 'institution'] = dict_outhor['institutions'][0]['display_name']
                            citing_institutions.loc[c, 'country'] = dict_outhor['institutions'][0]['country_code']
                        c += 1
                citing_institutions.drop_duplicates(inplace=True)
                return df['cited_by_count'].sum(), citing_institutions
            #except KeyError:
            #    return 0
        else:
            ans = requests.get("%s&page=1&per-page=200" % self.object['cited_by_api_url'])
            j_ans = json.loads(ans.text.encode('utf-8'))
            page = 2
            counts = 0
            df_list = list()
            while j_ans['results'].__len__() > 0:
                df = pd.DataFrame(j_ans['results'])
                df_list.append(df)
                counts += df['cited_by_count'].sum()
                ans = requests.get("%s&page=%s&per-page=200" % (self.object['cited_by_api_url'], page))
                j_ans = json.loads(ans.text.encode('utf-8'))
                page +=1
            df = pd.concat(df_list, axis=0)
            c = 0
            citing_institutions = pd.DataFrame()
            # print(df.columns)
            for i in df.index:
                try:
                    el = df.loc[i, 'authorships'].values[0]
                    doiOfIter = df.loc[i, 'doi'].values[0]
                except AttributeError:
                    el = df.loc[i, 'authorships']
                    doiOfIter = df.loc[i, 'doi']
                for dict_outhor in el:
                    citing_institutions.loc[c, 'service'] = self.service
                    citing_institutions.loc[c, 'platform'] = self.plaftorm
                    citing_institutions.loc[c, 'doi'] = self.doi
                    citing_institutions.loc[c, 'doiOfCiting'] = doiOfIter
                    # citing_institutions.loc[c, 'author'] = dict_outhor['author']['display_name']
                    if len(dict_outhor['institutions']) == 0:
                        citing_institutions.loc[c, 'institution'] = np.NAN
                        citing_institutions.loc[c, 'country'] = np.NAN
                    else:
                        citing_institutions.loc[c, 'institution'] = dict_outhor['institutions'][0]['display_name']
                        citing_institutions.loc[c, 'country'] = dict_outhor['institutions'][0]['country_code']
                    c += 1
            citing_institutions.drop_duplicates(inplace=True)
            return counts, citing_institutions


class OpenAlexService:

    def __init__(self, service, platform, doiString: str) -> None:
        self.service = service
        self.platform = platform
        self.doiSplit = [el.strip() for el in doiString.split(',')]
        self.openAlexDict: dict = {doi: OpenAlexDoi(service, platform, doi) for doi in self.doiSplit}
        self.citations = sum([el.citations for el in self.openAlexDict.values()])
        OfCiting = [el.get_citing_works() for el in self.openAlexDict.values()]
        self.citationsOfCiting = sum([el[0] for el in OfCiting if el[0] is not None])
        self.institutionsOfCiting = pd.concat([el[1] for el in OfCiting if el[1] is not None], axis=0)
        del OfCiting
        self.institutions = None
        try:
            self.institutions = pd.concat([el.get_institutions() for el in self.openAlexDict.values()],
                                          axis=0,
                                          ignore_index=True).drop_duplicates().reset_index(drop=True)
        except ValueError:
            print(service, doiString)

        if self.openAlexDict.__len__() > 1:
            self.counter_in_merger = 0
            citdf_list = list()
            for doi, obj in self.openAlexDict.items():
                citdf = obj.cit_by_years
                if citdf.shape[0] > 0:
                    citdf.columns = ['year', doi]
                    citdf_list.append(citdf)
            self.mgd_citby_year = reduce(lambda x, y: x.merge(y, on='year', how='outer'), citdf_list)

        else:
            key = list(self.openAlexDict.keys())[0]
            self.mgd_citby_year = self.openAlexDict[key].cit_by_years
            self.mgd_citby_year.columns = ['year', key]
        self.mgd_citby_year.index = self.mgd_citby_year['year']
        self.mgd_citby_year.drop(['year'], axis=1, inplace=True)
        self.mgd_citby_year.fillna(0, inplace=True)
        self.mgd_citby_year = self.mgd_citby_year.T
        self.mgd_citby_year['provider'] = 'OpenAlex'
        # self.authors = pd.concat([el.authors for el in self.openAlexList], axis=0,
        #                               ignore_index=True)
        # self.authors.drop_duplicates().reset_index(drop=True)
        # self.auth2orcid = pd.concat([el.auth2orcid for el in self.openAlexList], axis=0,
        #                               ignore_index=True).drop_duplicates().reset_index(drop=True)

    # def mg_citby_year(self, obj_df1: pd.DataFrame, obj_df2: pd.DataFrame) -> pd.DataFrame:
    #     if obj_df2.shape[0] != 0:
    #         # obj_df1_cols = list(obj_df1.columns)
    #         obj_df2_cols = list(obj_df2.columns)
    #         # obj_df1_cols.pop(-1)
    #         obj_df2_cols.pop(-1)
    #         # obj_df1_cols.append("doi_%s" % self.counter_in_merger)
    #         # self.counter_in_merger += 1
    #         obj_df2_cols.append("doi_%s" % self.counter_in_merger)
    #         self.counter_in_merger += 1
    #         # obj_df1.columns = obj_df1_cols
    #         obj_df2.columns = obj_df2_cols
    #         return obj_df1.merge(obj_df2, on='year', how='outer')
    #     else:
    #         return obj_df1


class MyCitationOverview(CitationOverview):

    def __init__(self, identifier, servname, apykey,
                 start=dt.now().timetuple()[0]-20,
                 end=dt.now().timetuple()[0],
                 id_type='doi'):
        super().__init__(identifier=identifier, start=start, end=end,
                         id_type=id_type,
                         apykey=apykey)

        self.start = start
        self.end = end
        self.servname = servname

    @property
    def cit4year(self) -> pd.DataFrame:
        timeline_df = [[tx[1] for tx in el] for el in self.cc]
        timeline_df = pd.DataFrame(timeline_df)
        timeline_df.columns = range(self.start, self.end + 1)
        timeline_df.index = self.doi
        #timeline_df['sum'] = self.rangeCount
        timeline_df['provider'] = 'Scopus'
        return timeline_df


def return_time(message: str = None):
    t = dt.now()
    s = str(t).split('.')[0]
    if message is None:
        print("[%s] Return time: e' l'ora dei teletubbies" % s)
    else:
        print("[%s] %s" % (s, message))
#
# def queryScopus(doi):
#     url = ("http://api.elsevier.com/content/search/scopus?query=doi(%s)" % doi)
#     resp = requests.get(url, headers={'Accept':'application/json','X-ELS-APIKey': MY_API_KEY})
#     return json.loads(resp.text.encode('utf-8'))


# def qSList(doiString: str) -> int:
#     doiSplit = doiString.split(', ')
#     # print(doiString)
#     res = list()
#     for el in doiSplit:
#         try:
#             res.append(int(queryScopus(el)['search-results']['entry'][0]['citedby-count']))
#         except KeyError:
#             pass
#     return sum(res)


if __name__ == '__main__':
    print("""
    ################################################################################################
    #                                                                                              #
    #      CITATION OVERVIEW SYSTEM FOR BIBLIOMETRIC ASSESSMENT RELYING ON OPENALEX AND SCOPUS     #
    #                                    POWERED BY ELIXIR-IIB                                     #
    #                                                                                              #
    ################################################################################################
    """)

    options = input_options()

    input_xlsx, output_dir, alex_key, scopus_key = options.input_excel, options.output_directory, \
        options.openalex_key, options.pybliometrics_key
    pybliometrics.scopus.create_config(keys=[scopus_key])
    pybliometrics.scopus.init()
    # home = os.environ['HOME']
    # config = os.path.join(home, '.config')
    # cfgfile = os.path.join(home, '.config', 'pybliometrics.cfg')
    # try:
    #     os.mkdir(os.path.join(home, '.config'))
    # except FileExistsError:
    #     pass
    # with open(cfgfile, 'wt') as cfg:
    #     cfg.write("[Directories]\n")
    #     cfg.write("AbstractRetrieval = %s/.pybliometrics/Scopus/abstract_retrieval\n" % config)
    #     cfg.write("AffiliationSearch = %s/.pybliometrics/Scopus/affiliation_search\n" % config)
    #     cfg.write("AuthorRetrieval = %s/.pybliometrics/Scopus/author_retrieval\n" % config)
    #     cfg.write("AuthorSearch = %s/.pybliometrics/Scopus/author_search\n" % config)
    #     cfg.write("CitationOverview = %s/.pybliometrics/Scopus/citation_overview\n" % config)
    #     cfg.write("AffiliationRetrieval = %s/.pybliometrics/Scopus/affiliation_retrieval\n" % config)
    #     cfg.write("ScopusSearch = %s/.pybliometrics/Scopus/scopus_search\n" % config)
    #     cfg.write("SerialTitle = %s/.pybliometrics/Scopus/serial_title\n\n" % config)
    #     cfg.write("[Authentication]\n")
    #     cfg.write("APIKey = %s \n\n" % scopus_key)
    #     cfg.write("[Requests]\n")
    #     cfg.write("Timeout = 20\n")
    #     cfg.write("Retries = 5\n")
    # exit()
    # import pybliometrics
    # print(pybliometrics.scopus.CONFIG_FILE)
    # pybliometrics.scopus.init(keys=scopus_key,config_dir=cfgfile)
    #
    print("""
    Input excel file: %s
    Output directory: %s
    Openalex key: %s
    Scopus key: %s
    ______________________________________________________________________________________
    """ % (input_xlsx, output_dir, alex_key, scopus_key))

    src = pd.read_excel(input_xlsx)
    src = src[~src['Primary doi first then others'].isna()]
    zinput = zip(src['Service'],src['Platform'], src['Primary doi first then others'])
    return_time('Starting OpenAlex information retrieval...')
    OpenAlexServiceDict = {x:OpenAlexService(x,y,z) for x,y,z in zinput}
    return_time('Starting OpenAlex citations data elaboration...')
    src['OpenAlexCitations'] = [el.citations for el in OpenAlexServiceDict.values()]
    return_time('Starting OpenAlex impact data elaboration...')
    src['OpenAlexCitationsOfCiting'] = [el.citationsOfCiting for el in OpenAlexServiceDict.values()]
    institutions = pd.concat([el.institutions for el in OpenAlexServiceDict.values()],
                             axis=0, ignore_index=True)
    institutionsOfCitings = pd.concat([el.institutionsOfCiting for el in OpenAlexServiceDict.values()],axis=0)
    zinput = zip(src['Service'], src['Primary doi first then others'])
    return_time('Starting Starting Scopus information retrieval...')

    PyBlioInstanceDict = {a:MyCitationOverview(
        servname=a, identifier=[el.strip() for el in b.split(',')],
        start=dt.now().timetuple()[0]-20,
        end=dt.now().timetuple()[0], id_type='doi',
        apykey=scopus_key) for a, b in zinput}
    src['PyBlioCitations'] = [el.grandTotal for el in PyBlioInstanceDict.values()]
    return_time('Starting overall data storage...')
    try:
        os.mkdir(output_dir)
    except FileExistsError:
        pass

    with pd.ExcelWriter(os.path.join(output_dir, 'ELIXIR.IT_IMPACT.xlsx')) as buf:
        src.to_excel(buf, sheet_name='summary')
        institutions.to_excel(buf, sheet_name='institutions')
        institutionsOfCitings.to_excel(buf, sheet_name='institutionsOfCitings')
    return_time('Starting service-specific data storage...')
    dir_services=os.path.join(output_dir, "services")
    try:
        os.mkdir(dir_services)
    except FileExistsError:
        pass
    for k, df in OpenAlexServiceDict.items():
        return_time(k)
        # print(df.mgd_citby_year)
        # print(PyBlioInstanceDict[k].cit4year)
        aux = pd.concat([PyBlioInstanceDict[k].cit4year, df.mgd_citby_year], axis=0)
        aux.replace(np.nan, 0, inplace=True)
        aux.to_csv(os.path.join(dir_services, re.sub(r"[/@)(]", "_", k)))
return_time('Finished...Good bye')