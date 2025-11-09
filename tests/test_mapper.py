from esg_pipeline.mapping.mapper import map_to_schema

# smoke test with trivial input
rows = [{'field':'GHG_Scope1','value':123,'confidence':0.7}]
map_to_schema(rows, 'schema/esg_schema.json', threshold=10)
