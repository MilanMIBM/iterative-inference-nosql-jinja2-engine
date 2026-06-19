import marimo

__generated_with = "0.23.10"
app = marimo.App(width="full")

with app.setup:
    import marimo as mo
    import pandas as pd
    import time
    import uuid
    import sys
    import os
    import io


@app.cell
def _():
    import sparqldataframe

    return (sparqldataframe,)


@app.cell
def _():
    notice_nr = "116649-2025"
    notice_nr_filter = f'FILTER (?publicationNumber = "00{notice_nr}")'
    return (notice_nr_filter,)


@app.cell
def _(notice_nr_filter):
    sparql_query = f"""PREFIX epo: <http://data.europa.eu/a4g/ontology#>

    CONSTRUCT {{
      ?s ?p ?o .
    }}

    WHERE {{

      # Change this to the publication number you want to look up
      {notice_nr_filter}

      # Find the named graph for this notice
      GRAPH ?g {{
        ?notice a epo:Notice ;
                epo:hasNoticePublicationNumber ?publicationNumber .
      }}

      # Return all triples from that graph
      GRAPH ?g {{
        ?s ?p ?o .
      }}
    }}"""
    print(sparql_query)
    return (sparql_query,)


@app.cell
def _():
    publication_endpoint = "https://publications.europa.eu/webapi/rdf/sparql"
    return (publication_endpoint,)


@app.cell
def _(publication_endpoint, sparql_query, sparqldataframe):
    sqpl_df = sparqldataframe.query(publication_endpoint, sparql_query)
    sqpl_df
    return (sqpl_df,)


@app.cell
def _(sqpl_df):
    pd.DataFrame(sqpl_df)
    return


if __name__ == "__main__":
    app.run()
