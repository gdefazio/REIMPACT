import os.path

from pybliometrics.scopus import CitationOverview
# from itertools import combinations
from functools import reduce
import pandas as pd
import numpy as np
import argcomplete
import argparse
import requests
import pyalex
import json
import re

# '10.1093/nar/gkr930, 10.1093/nar/gkt1115, 10.1093/nar/gkp983, 10.1093/nar/gkl950, 10.1016/s0014-5793(01)03293-8, 10.1002/cpbi.93, 10.1002/cpbi.93'
# MY_API_KEY = '8fc3c1e2aaaf954888ae7cba80324151'


def input_options():
    parser = argparse.ArgumentParser(
        description="This script interrogates OpenAlex and Scopus Api to obtain bibliometric features of papers related to ELIXIR IT services",
        prefix_chars="-")
    parser.add_argument("-i", "--input_excel", type=str,
                        help="The path to the input excel. An excel format example is provided in the GitHub page",
                        action="store", required=False,
                        default='./Table S1-SAB-160224_lst.xlsx')
    parser.add_argument("-o", "--output_directory", type=str,
                        help="output directory", action="store", required=False,
                        default="./")
    parser.add_argument("-a", "--openalex_key", type=str,
                        help="the OpenAlex API key to query",
                        action="store", required=False,
                        default='8fc3c1e2aaaf954888ae7cba80324151')
    parser.add_argument("-p", "--pybliometrix_key", type=str,
                        help="the OpenAlex API key to query",
                        action="store", required=False,
                        default='b3effd27f35c5a12b039321e01d7d740')

    argcomplete.autocomplete(parser)
    return parser.parse_args()


class OpenAlexDoi:

    def __init__(self, service, doi) -> None:
        self.service = service
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
                melt_info.extend(self.authors.loc[i, 'raw_affiliation_strings'])
                # df = pd.DataFrame(
                #     self.authors.loc[i, 'institutions'])[[
                #     'display_name', 'country_code', 'type']]
                # # df.loc[:,'author'] = self.authors.loc[i, 'raw_author_name']
                # melt_info.append(df)
        melt_info = set(melt_info)
        # try:
        #     melt = pd.concat(melt_info, axis=0, ignore_index=True, sort=False)
        #     melt.drop_duplicates()
        melt = pd.DataFrame(melt_info, columns=['institution'])
        melt['weigh'] = self.citations
        melt['service'] = self.service
        melt['doi'] = self.doi
            # melt.reset_index(inplace=True, drop=True)
        return melt
        # except Exception as e:
        #     print(e)

    def get_citing_works(self) -> int:
        if self.citations <= 200:
            ans = requests.get(self.object['cited_by_api_url'])
            j_ans = json.loads(ans.text.encode('utf-8'))
            try:
                return pd.DataFrame(j_ans['results'])['cited_by_count'].sum()
            except KeyError:
                return 0
        else:
            ans = requests.get("%s&page=1&per-page=200" % self.object['cited_by_api_url'])
            j_ans = json.loads(ans.text.encode('utf-8'))
            page = 2
            counts = 0
            while j_ans['results'].__len__() > 0:
                counts += pd.DataFrame(j_ans['results'])['cited_by_count'].sum()
                ans = requests.get("%s&page=%s&per-page=200" % (self.object['cited_by_api_url'], page))
                j_ans = json.loads(ans.text.encode('utf-8'))
                page +=1

            return counts


class OpenAlexService:

    def __init__(self, service, doiString: str) -> None:
        self.service = service
        self.doiSplit = [el.strip() for el in doiString.split(',')]
        self.openAlexList: list = [OpenAlexDoi(service, el) for el in self.doiSplit]
        self.citations = sum([el.citations for el in self.openAlexList])
        self.citationsOfCiting = sum([el.get_citing_works() for el in self.openAlexList])
        self.institutions = None
        try:
            self.institutions = pd.concat([el.get_institutions() for el in self.openAlexList], axis=0,
                                      ignore_index=True).drop_duplicates().reset_index(drop=True)
        except ValueError:
            print(service, doiString)

        if self.openAlexList.__len__() > 1:
            self.counter_in_merger = 0
            self.mgd_citby_year = reduce(lambda x, y: self.mg_citby_year(x, y),
                                         [el.cit_by_years for el in self.openAlexList])
        else:
            self.mgd_citby_year = self.openAlexList[0].cit_by_years

        self.mgd_citby_year.fillna(0, inplace=True)
        # self.authors = pd.concat([el.authors for el in self.openAlexList], axis=0,
        #                               ignore_index=True)
        # self.authors.drop_duplicates().reset_index(drop=True)
        # self.auth2orcid = pd.concat([el.auth2orcid for el in self.openAlexList], axis=0,
        #                               ignore_index=True).drop_duplicates().reset_index(drop=True)

    def mg_citby_year(self, obj_df1: pd.DataFrame, obj_df2: pd.DataFrame) -> pd.DataFrame:
        if obj_df2.shape[0] != 0:
            # obj_df1_cols = list(obj_df1.columns)
            obj_df2_cols = list(obj_df2.columns)
            # obj_df1_cols.pop(-1)
            obj_df2_cols.pop(-1)
            # obj_df1_cols.append("doi_%s" % self.counter_in_merger)
            # self.counter_in_merger += 1
            obj_df2_cols.append("doi_%s" % self.counter_in_merger)
            self.counter_in_merger += 1
            # obj_df1.columns = obj_df1_cols
            obj_df2.columns = obj_df2_cols
            return obj_df1.merge(obj_df2, on='year', how='outer')
        else:
            return obj_df1


class MyCitationOverview(CitationOverview):

    def __init__(self, identifier, servname, start=2000, end=2024,
                 id_type = 'doi',
                 apykey = 'b3effd27f35c5a12b039321e01d7d740'):
        super().__init__(identifier=identifier, start=start, end=end,
                         id_type = id_type,
                         apykey = apykey)
        self.start = start
        self.end = end
        self.servname = servname

    @property
    def cit4year(self) -> pd.DataFrame:
        timeline_df = [[tx[1] for tx in el] for el in self.cc]
        timeline_df = pd.DataFrame(timeline_df)
        timeline_df.columns = range(self.start, self.end+1)
        timeline_df['sum'] = self.rangeCount
        return timeline_df

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
    options = input_options()
    input_xlsx, output_dir, alex_key, scopus_key = options.input_excel, options.output_directory, \
        options.openalex_key, options.pybliometrix_key
    src = pd.read_excel(input_xlsx)
    src = src[~src['Primary doi first then others'].isna()]
    zinput = zip(src['Service'], src['Primary doi first then others'])
    OpenAlexServiceList = [OpenAlexService(x,y) for x,y in zinput]
    src['OpenAlexCitations'] = [el.citations for el in OpenAlexServiceList]
    src['OpenAlexCitationsOfCiting'] = [el.citationsOfCiting for el in OpenAlexServiceList]
    institutions = pd.concat([el.institutions for el in OpenAlexServiceList], axis=0, ignore_index=True)
    with pd.ExcelWriter(os.path.join(output_dir, 'ELIXIR.IT_IMPACT_OpenAlex.xlsx')) as buf:
        src.to_excel(buf, sheet_name='summary')
        institutions.to_excel(buf, sheet_name='institutions')
        for df in OpenAlexServiceList:
            aux = df.mgd_citby_year.copy()
            aux.replace(np.nan, 0, inplace=True)
            aux['sum'] = aux.loc[:, aux.columns[1:]].sum(axis=1)
            aux.to_excel(buf, sheet_name=re.sub(r"[/@)(]", "_", df.service))

    src4PyB = src.copy()
    zinput = zip(src4PyB['Service'], src4PyB['Primary doi first then others'])
    PyBlioInstance = [MyCitationOverview(
        servname=a, identifier=[el.strip() for el in b.split(',')],
        start=2000, end=2024, id_type='doi',
        apykey=scopus_key) for a, b in zinput]
    src4PyB['PyBlioCitations'] = [el.grandTotal for el in PyBlioInstance]
    with pd.ExcelWriter(os.path.join(output_dir, 'ELIXIR.IT_IMPACT_PyBliometrix.xlsx')) as buf:
        src4PyB.to_excel(buf, sheet_name='summary')
        for inst in PyBlioInstance:
            inst.cit4year.to_excel(buf, sheet_name=re.sub(r"[/@)(]", "_", inst.servname))
