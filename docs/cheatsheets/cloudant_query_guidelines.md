# Working with IBM Cloudant Query

IBM Cloudant Query is a flexible query language that allows fetching documents from a database that match a "selector" -- a JSON object that defines the search criteria.

How IBM Cloudant Query works

To use IBM Cloudant Query, you send JSON-formatted queries to the _find HTTP endpoint of a database. The JSON contains a selector which defines the query itself, alongside metadata such as the sort order to use when returning documents. The selector syntax is loosely based on MongoDB's query language, offering a rich set of query operators that can be combined to make complex queries.

Start learning about queries by reading Selector syntax.

To ensure queries return results quickly, IBM Cloudant Queries should be backed by a suitable secondary index. There are two types of indexes available:

JSON indexes (type=json, the default) - a set of nominated document fields combined together to form the index keyspace. A query's selector and sort parameters must match an index's keys for it to be used when processing the query.
Text indexes (type=text) - a set of nominated document fields indexed separately. One or more of the indexed fields can be combined in selector expressions to extract small slices of data (up to 200 documents per query).
IBM Cloudant queries can act on the entire database, or for partitioned databases, on a single partition.

Learn about creating indexes by reading:

Working with JSON indexes.
Working with text indexes.
Partial indexes.
When to use IBM Cloudant Query

IBM Cloudant Query is ideal for:

Operational queries where a query's selector/sort match a pre-defined type=json index.
Ad-hoc queries on one or more fields backed by a type=text index, for small result sets.
Creating partial indexes, where a subset of the documents are used to form the index and the selector/sort further filters the indexed data.
When not to use IBM Cloudant Query

Avoid Query for:

Data aggregation. Use Views instead.
Free-text or wildcard searching. Use Cloudant Search instead.

--- --- ---

## Query selector syntax

The IBM Cloudant Query language is expressed as a JSON object that describes documents of interest. Within this structure, you can apply conditional logic by using specially named fields.

The IBM Cloudant Query language has some similarities with MongoDB query documents, but these similarities arise from a commonality of purpose and don't necessarily extend to equivalence of function or result.

Selector basics

Elementary selector syntax requires you to specify one or more fields, and the corresponding values needed for those fields. The following example selector matches all documents that have a director field that contains the value Lars von Trier.

See the following example of a simple selector:

{
 "selector": {
  "director": "Lars von Trier"
 }
}
If you created a full text index by specifying "type":"text" when the index was created, you can use the $text operator to select matching documents. In the following example, the full text index is inspected to find any document that contains the word Bond.

See the following example of a simple selector for a full_text index:

{
 "selector": {
  "$text": "Bond"
 }
}
You can create more complex selector expressions by combining operators. However, for IBM Cloudant Query indexes of type json, you can't use "combination" or "array logical" operators such as $regex as the basis of a query. Only the equality operators such as $eq, $gt, $gte, $lt, and $lte - but not $ne - can be used as the basis of a more complex query. For more information about creating complex selector expressions, see Creating selector expressions.

Selector with two fields

In the following example, the selector matches any document with a name field that contains Paul, and that also has a location field with the value "Boston".

See the following example of a more complex selector:

{
 "selector": {
  "name": "Paul",
  "location": "Boston"
 }
}
Subfields

Use a more complex selector to specify the values for a field of nested objects, or subfields. For example, you might use a standard JSON structure for specifying a field and a subfield.

See the following example of a field and subfield selector within a JSON object:

{
 "selector": {
  "imdb": {
   "rating": 8
  }
 }
}
An abbreviated equivalent uses a dot notation to combine the field and subfield names into a single name.

See the following example of an equivalent field and subfield selector that uses dot notation:

{
 "selector": {
  "imdb.rating": 8
 }
}
Building more complex selector expressions

In general, whenever you have an operator that takes an argument, that argument can itself be another operator with arguments of its own. This expansion enables more complex selector expressions.

Combination or array logical operators, such as $regex, can result in a full database scan when you use indexes of type JSON, resulting in poor performance. Only equality operators, such as $eq, $gt, $gte, $lt, and $lte (but not $ne), enable index lookups. To ensure that indexes are used effectively, analyze the explain plan for each query.

Most selector expressions work exactly as you would expect for the operator. The matching algorithms that are used by the $regex operator are currently based on the Perl Compatible Regular Expression (PCRE) library. However, not all of the PCRE library is implemented. Additionally, some parts of the $regex operator go beyond what PCRE offers. For more information about what is implemented, see the Erlang Regular Expression information.

Using the $text operator

The $text operator is based on a Lucene search with a standard analyzer. The operator isn't case-sensitive, and matches on any words. However, the $text operator doesn't support full Lucene syntax, such as wildcards, fuzzy matches, or proximity detection.

For more information, see the Search documentation. The $text operator applies to all strings found in the document. If you place this operator in the context of a field name, it's invalid.

--- --- ---

### Query operators

Operators are identified by the use of a dollar sign ($) prefix in the name field.

The selector syntax has two core types of operators:

Combination operators
Condition operators
In general, combination operators are applied at the topmost level of selection. They're used to combine conditions, or to create combinations of conditions, into one selector.

Every explicit operator has the form:

{
 "$operator": "argument"
}
A selector without an explicit operator is considered to have an implicit operator. The exact implicit operator is determined by the structure of the selector expression.

Implicit operators

The two implicit operators are shown in the following list:

"Equality"
"And"
In a selector, any field that contains a JSON value, but that has no operators in it, is considered to be an equality condition. The implicit equality test also applies for fields and subfields.

Any JSON object that isn't the argument to a condition operator is an implicit $and operator on each field.

See the following example selector that uses an operator to match any document, where the year field has a value greater than 2010:

{
 "selector": {
  "year": {
   "$gt": 2010
  }
 }
}
In the following example, a matching document must have a field that is called director, and the field must have a value exactly equal to Lars von Trier.

See the following example of the implicit equality operator:

{
 "director": "Lars von Trier"
}
You can also make the equality operator explicit, as shown in the following example.

See the following example of an explicit equality operator:

{
 "director": {
  "$eq": "Lars von Trier"
 }
}
In the following example that uses subfields, the field imdb in a matching document must also have a subfield rating, and the subfield must have a value equal to 8.

See the following example of implicit operator that is applied to a subfield test:

{
 "imdb": {
  "rating": 8
 }
}
You can make the equality operator explicit.

See the following example of an explicit equality operator:

{
 "selector": {
  "imdb": {
   "rating": { "$eq": 8 }
  }
 }
}
See the following example of a $eq operator that is used with full text indexing:

{
 "selector": {
  "year": {
   "$eq": 2001
  }
 },
 "sort": [
  "title:string"
 ],
 "fields": [
  "title"
 ]
}
See the following example of an $eq operator that is used with a database that is indexed on the field year:

{
 "selector": {
  "year": {
   "$eq": 2001
  }
 },
 "sort": [
  "year"
 ],
 "fields": [
  "year"
 ]
}
In the following example, the field director must be present and contain the value Lars von Trier and the field year must exist and have the value 2003.

See the following example of an implicit $and operator:

{
 "director": "Lars von Trier",
 "year": 2003
}
You can make both the $and operator and the equality operator explicit.

See the following example that uses explicit $and and $eq operators:

{
 "$and": [
  {
   "director": {
    "$eq": "Lars von Trier"
   }
  },
  {
   "year": {
    "$eq": 2003
   }
  }
 ]
}
Explicit operators

All operators, apart from the $eq (equality) and $and (and) operators, must be stated explicitly.

Combination operators

Combination operators are used to combine selectors. Three combination operators ($all, $allMatch, and $elemMatch) help you work with JSON arrays, in addition to the common Boolean operators found in most programming languages.

A combination operator takes a single argument. The argument is either another selector, or an array of selectors.

Operator
Argument
Purpose
$all Array Matches an array value if it contains all the elements of the argument array.
$allMatch Selector Matches and returns all documents that contain an array field, where all the elements match all the specified query criteria.
$and Array Matches if all the selectors in the array match.
$elemMatch Selector Matches and returns all documents that contain an array field with at least one element that matches all the specified query criteria.
$nor Array Matches if none of the selectors in the array match.
$not Selector Matches if the selector doesn't match.
$or Array Matches if any of the selectors in the array match. All selectors must use the same index.
Table 1. Combination operators

$all

The $all operator matches an array value if it contains all the elements of the argument array.

See the following example that uses the $all operator:

{
 "selector": {
  "genre": {
   "$all": ["Comedy","Short"]
  }
 },
 "fields": [
  "title",
  "genre"
 ],
 "limit": 10
}
$allMatch

The $allMatch operator matches and returns all documents that contain an array field, where all the elements in the array field match the supplied query criteria.

See the following example that uses the $allMatch operator:

{
    "genre": {
        "$allMatch": {
          "$eq": "Horror"
        }
    }
}
$and

The $and operator matches if all the selectors in the array match.

See the following example that uses the $and operator:

{
    "selector": {
        "$and": [
            {
                "year": {
                    "$in": [2014, 2015]
                }
            },
            {
                "genre": {
                     "$all": ["Comedy","Short"]
                 }
            }
        ]
    },
    "fields": [
        "year",
        "_id",
        "title"
    ],
    "limit": 10
}

$elemMatch

The $elemMatch operator matches and returns all documents that contain an array field with at least one element that matches the supplied query criteria.

See the following example that uses the $elemMatch operator:

{
 "selector": {
  "genre": {
   "$elemMatch": {
    "$eq": "Horror"
   }
  }
 },
 "fields": [
  "title",
  "genre"
 ],
 "limit": 10
}
$nor

The $nor operator matches if the selector does not match.

See the following example that uses the $nor operator:

{
 "selector": {
  "year": {
   "$gte": 1900,
   "$lte": 1910
  },
  "$nor": [
   { "year": 1901 },
   { "year": 1905 },
   { "year": 1907 }
  ]
 },
 "fields": [
  "title",
  "year"
 ]
}

$not

The $not operator matches if the selector does not resolve to a value of true.

See the following example that uses the $not operator:

{
 "selector": {
  "year": {
   "$gte": 1900,
   "$lte": 1903
  },
  "$not": {
   "year": 1901
  }
 },
 "fields": [
  "title",
  "year"
 ]
}

$or

The $or operator matches if any of the selectors in the array match.

See the following example that uses the $or operator:

{
 "selector": {
  "year": 1977,
  "$or": [
   { "director": "George Lucas" },
   { "director": "Steven Spielberg" }
  ]
 },
 "fields": [
  "title",
  "director",
  "year"
 ]
}
Condition operators

Condition operators are specific to a field, and are used to evaluate the value that is stored in that field. For instance, the $eq operator matches when the specified field contains a value that is equal to the supplied argument.

The basic equality and inequality operators common to most programming languages are supported. Some "meta" condition operators are also available.

Some condition operators accept any valid JSON content as the argument. Other condition operators require the argument to be in a specific JSON format.

Operator type
Operator
Argument
Purpose
(In) equality $lt Any JSON The field is less than the argument.
$lte Any JSON The field is less than or equal to the argument.
$eq Any JSON The field is equal to the argument.
$ne Any JSON The field isn't equal to the argument.
$gte Any JSON The field is greater than or equal to the argument.
$gt Any JSON The field is greater than the argument.
Object $exists Boolean Check whether the field exists or not, no matter what its value is.
$type String Check the document field's type. Accepted values are null, boolean, number, string, array, and object.
Array $in Array of JSON values The document field must exist in the list provided.
$nin Array of JSON values The document field must not exist in the list provided.
$size Integer Special condition to match the length of an array field in a document. Non-array fields can't match this condition.
Miscellaneous $mod [Divisor, Remainder] Divisor and Remainder are both positive or negative integers. Non-integer values result in a 404 status. Matches documents where the expression (field % Divisor == Remainder) is true, and only when the document field is an integer.
$regex String A regular expression pattern to match against the document field. Matches only when the field is a string value and matches the supplied regular expression.
Table 2. Condition operator argument requirements

Tip: Regular expressions don't work with indexes, so they must not be used to filter large data sets. However, they can be used to restrict a partial index <find/partial_indexes>.

$lt

The $lt operator matches if the specified field content is less than the argument.

See the following example that uses the $lt operator with full-text indexing:

{
 "selector": {
  "year": {
   "$lt": 1900
  }
 },
 "sort": [
  "year:number",
  "title:string"
 ],
 "fields": [
  "year",
  "title"
 ]
}

See the following example that uses the $lt operator with a database that is indexed on the field year:

{
 "selector": {
  "year": {
   "$lt": 1900
  }
 },
 "sort": [
  "year"
 ],
 "fields": [
  "year"
 ]
}
$lte

The $lte operator matches if the specified field content is less than or equal to the argument.

See the following example that uses the $lte operator with full-text indexing:

{
 "selector": {
  "year": {
   "$lte": 1900
  }
 },
 "sort": [
  "year:number",
  "title:string"
 ],
 "fields": [
  "year",
  "title"
 ]
}

See the following example that uses the $lte operator with a database that is indexed on the field year:

{
 "selector": {
  "year": {
   "$lte": 1900
  }
 },
 "sort": [
  "year"
 ],
 "fields": [
  "year"
 ]
}
$eq

The $eq operator matches if the specified field content is equal to the supplied argument.

See the following example that uses the $eq operator with full-text indexing:

{
 "selector": {
  "year": {
   "$eq": 2001
  }
 },
 "sort": [
  "title:string"
 ],
 "fields": [
  "title"
 ]
}
See the following example that uses the $eq operator with a database that is indexed on the field year:

{
 "selector": {
  "year": {
   "$eq": 2001
  }
 },
 "sort": [
  "year"
 ],
 "fields": [
  "year"
 ]
}
$ne

The $ne operator matches if the specified field content isn't equal to the supplied argument.

Tip: The $ne operator can't be the basic (lowest level) element in a selector when you use an index of type json.

See the following example that uses the $ne operator with full-text indexing:

{
 "selector": {
  "year": {
   "$ne": 1892
  }
 },
 "fields": [
  "year"
 ],
 "sort": [
  "year:number"
 ]
}
See the following example that uses the $ne operator with a primary index:

{
 "selector": {
 "year": {
   "$ne": 1892
  }
 },
 "fields": [
  "year"
 ],
 "limit": 10
}
$gte

The $gte operator matches if the specified field content is greater than or equal to the argument.

See the following example that uses the $gte operator with full-text indexing:

{
 "selector": {
  "year": {
   "$gte": 2001
  }
 },
 "sort": [
  "year:number",
  "title:string"
 ],
 "fields": [
  "year",
  "title"
 ]
}

See the following example that uses the $gte operator with a database that is indexed on the field year:

{
 "selector": {
  "year": {
   "$gte": 2001
  }
 },
 "sort": [
  "year"
 ],
 "fields": [
  "year"
 ]
}
$gt

The $gt operator matches if the specified field content is greater than the argument.

See the following example that uses the $gt operator with full-text indexing:

{
 "selector": {
  "year": {
   "$gt": 2001
  }
 },
 "sort": [
  "year:number",
  "title:string"
 ],
 "fields": [
  "year",
  "title"
 ]
}

See the following example that uses the $gt operator with a database that is indexed on the field year:

{
 "selector": {
  "year": {
   "$gt": 2001
  }
 },
 "sort": [
  "year"
 ],
 "fields": [
  "year"
 ]
}
$exists

The $exists operator matches if the field exists, no matter what its value is.

See the following example that uses the $exists operator:

{
 "selector": {
  "year": 2015,
  "title": {
   "$exists": true
  }
 },
 "fields": [
  "year",
  "_id",
  "title"
 ]
}
$type

The $type operator requires that the specified document field is of the correct type.

See the following example that uses the $type operator:

{
 "selector": {
    "year": {
   "$type": "number"
  }
 },
 "fields": [
  "year",
  "_id",
  "title"
 ]
}
$in

The $in operator requires that the document field must exist in the list provided.

See the following example that uses the $in operator:

{
 "selector": {
    "year": {
   "$in": [2010, 2015]
  }
 },
 "fields": [
  "year",
  "_id",
  "title"
 ],
 "limit": 10
}
$nin

The $nin operator requires that the document field must not exist in the list provided.

See the following example that uses the $nin operator:

{
 "selector": {
    "year": {
   "$nin": [2010, 2015]
  }
 },
 "fields": [
  "year",
  "_id",
  "title"
 ],
 "limit": 10
}
$size

The $size operator matches the length of an array field in a document.

See the following example that uses the $size operator:

{
 "selector": {
    "genre": {
   "$size": 4
  }
 },
 "fields": [
  "title",
  "genre"
 ],
 "limit": 25
}
$mod

The $mod operator matches documents where the expression (field % Divisor == Remainder) is true, and only when the document field is an integer. The Divisor and Remainder must be integers. They can be positive or negative integers. A query where the Divisor or Remainder is a non-integer returns a 404 status.

Tip: When you use negative integer values for the Divisor or Remainder, the IBM® Cloudant® for IBM Cloud® $mod operator uses truncated division. Both the Erlang rem modulo operator, and the % operator in C, behave in a similar way.

See the following example that uses the $mod operator:

{
 "selector": {
          "year": {
   "$mod": [100,0]
  }
 },
 "fields": [
  "title",
  "year"
 ],
 "limit": 50
}
$regex

The $regex operator matches when the field is a string value and matches the supplied regular expression.

See the following example that uses the $regex operator:

{
 "selector": {
     "cast": {
   "$elemMatch": {
    "$regex": "^Robert"
   }
  }
 },
 "fields": [
  "title",
  "cast"
 ],
 "limit": 10
}

--- --- ---

### Query parameters

Query parameters change the output of IBM Cloudant Query requests, altering the sort order, fields returned or paginating responses. Parameters are supplied in the query, alongside the selector field.

Overview of parameters

This JSON document uses all available query parameters:

{
  // Query selector
 "selector": {
  "year": {
   "$gt": 2010
  }
 },
 // Specify fields to return
 "fields": ["_id", "_rev", "year", "title"],
 // Specify sort order
 "sort": [{"year": "asc"}],
 // Return a maximum number of results
 "limit": 10,
 // Start returning results from a previous bookmark (pagination)
 "bookmark":"g1AAAAA-eJzLYWBgYMpgSmHgKy5JLCrJTq2MT8lPzkzJB"
 // Hint to use a specific index for a query
 "use_index": "_design/32372935e14bed00cc6db4fc9efca0f1537d34a8",
 // Disallow using a different index than the specified index
  "allow_fallback": false
 }

Specifying fields to return

It's possible to specify which fields are returned for a document when you select from a database. This can offer advantages:

Your results are limited to only those parts of the document that are needed for your application.
A reduction in the size of the response.
The fields to return are specified using the fields array in the query. The provided field names can use dotted notation to access subfields.

This query will return only the four specified fields from the result documents:

{
 "selector": {
  "Actor_name": "Robert De Niro"
 },
 "fields": [
  "Actor_name",
  "Movie_year",
  "_id",
  "_rev"
 ]
}
Tip: Only the specified filter fields are included in the response._id or other metadata fields aren't automatically included.

Sorting results

Use the sort field in a query to specify how the returned results are ordered. The sort field contains a list of field name and direction pairs, expressed as an array. The first field name and direction pair are the topmost-level of sort. Further pairs, if provided, specify the next level of sort.

The sort field can be any field. Use dotted notation if needed for subfields.

The direction value is asc for ascending, and desc for descending:

"sort": [{ "fieldName1": "desc" }, { "fieldName2": "desc" }]
If you exclude the direction value, the default asc is used. For ascending sorting, the following shorthand can be used:

"sort": [ "fieldName1", "fieldName2" ]
A typical requirement is to search for some content by using a selector, then to sort the results according to the specified field, in the direction preferred.

To use sorting, an index containing the sort fields must be defined. If using json index, the fields must be specified in the same order as the sort.

Tip: Currently, IBM Cloudant Query doesn't support multiple fields with different sort orders, so the direction must either be all ascending or all descending.

If the direction is ascending, you can use a string instead of an object to specify the sort fields.

Sorting using text indexes

For field names in sort queries against a text index where the type of the field being sorted cannot be determined, it may be necessary for a field type to be specified. For example:

"sort": [ { "[fieldname]:string": "asc" } ]
Which index is used by query?
Field type requirement
JSON index None
Text index of all fields in all documents Specify the sort field in the query if the database contains documents where the sort field has one type. Also, specify the sort field in the query if it contains documents where the sort field has a different type.
Any other text index Specify the type of all sort fields in the query.
Table 1. When to specify the field type

Tip: A text index of all fields in all documents is created when you use the syntax: "index": {}.

The sorting order is undefined when fields contain different data types. This characteristic is an important difference between text and view indexes. Sorting behavior for fields with different data types might change in future versions.

Pagination

IBM Cloudant Query supports pagination by the bookmark field. Every _find response contains a bookmark - a token that IBM Cloudant uses to determine where to resume from when later queries are made. To get the next set of query results, add the bookmark that was received in the previous response to your next request. Remember to keep the selector the same, otherwise you receive unexpected results. To paginate backwards, you can use a previous bookmark to return the previous set of results.

For full documentation of pagination, see Pagination and bookmarks.

Tip: The presence of a bookmark doesn't guarantee more results. You can test whether you are at the end of the result set by comparing the number of results that are returned with the page size requested. If the results returned are less than limit, no more results were returned in the result set.

Hinting use of a specific index

To instruct a query to use a specific index, add the use_index parameter to the query. This is a hint; if the index cannot be used for the query, an alternative index will be used.

The value of the use_index parameter takes one of the following formats:

"use_index": "$DDOC"
"use_index": ["$DDOC","$INDEX_NAME"]
This example query shows hinting a specific index with use_index:

{
 "selector": {
  "$text": "Pacino",
  "year": 2010
 },
 "use_index": "_design/32372935e14bed00cc6db4fc9efca0f1537d34a8"
}
Forcing use of a specific index

Combine the allow_fallback parameter with use_index to force the use of a specific index. If the index cannot be used for the query, the query will return an error response.

Using "allow_fallback": false without specifying use_index will prevent use of the _all_docs built-in index.

This example query shows forcing a specific index by using allow_fallback with use_index:

{
 "selector": {
  "$text": "Pacino",
  "year": 2010
 },
 "use_index": "_design/32372935e14bed00cc6db4fc9efca0f1537d34a8",
  "allow_fallback": false
}

--- --- ---

### JSON indexes

JSON indexes are IBM Cloudant Query indexes that are excellent for equality ($eq) and range ($lt, $lte, $gte and $gte) queries. Create JSON indexes to support queries that include these operators.

Creating JSON indexes

To create a JSON index in the database $DATABASE, make a POST request to /$DATABASE/_index with a JSON object that describes the index in the request body. The type field of the JSON object must be set to json. A JSON index can be partitioned or global; this option is set by using the partitioned field.

See the following example that uses HTTP to request an index of type JSON:

POST /$DATABASE/_index HTTP/1.1
Content-Type: application/json
See the following example of a JSON object that creates a partitioned index that is called foo-partitioned-index for the field called foo:

{
    "index": {
        "fields": ["foo"]
    },
    "name" : "foo-partitioned-index",
    "type" : "json",
    "partitioned": true
}
See the following example of a JSON object that creates a global index that is called bar-global-index for the field called bar:

{
    "index": {
        "fields": ["bar"]
    },
    "name" : "bar-global-index",
    "type" : "json",
    "partitioned": false
}
See the following example of returned JSON, confirming that the index was created:

{
    "result": "created"
}
Field
Description
index fields - A JSON array of field names that uses the sort syntax. Nested fields are also allowed, for example, person.name.
ddoc (optional) Name of the design document in which the index is created. By default, each index is created in its own design document. Indexes can be grouped into design documents for efficiency. However, a change to one index in a design document invalidates all other indexes in the same document.
type (optional) Can be json or text. Defaults to json.
name (optional) Name of the index. If no name is provided, a name is generated automatically.
partitioned (optional, boolean) Determines whether this index is partitioned. For more information, see the partitioned field.
Table 1. Request body format

The partitioned field

This field sets whether the created index is a partitioned or global index.

Value
Description
Notes
true Create the index as partitioned. Can be used only in a partitioned database.
false Create the index as global. Can be used in any database.
Table 2. Partitioned field values

The default follows the partitioned setting for the database:

Is the database partitioned?
Default partitioned value
Allowed values
Yes true true, false
No false false
Table 3. Default partitioned value

Important: It's important to reiterate that the default partitioned value is true for indexes that are created in a partitioned database. This default value means that the index cannot be used to satisfy global queries.

Code
Description
200 Index was created successfully or existed in the database.
400 Bad request - the request body doesn't have the specified format.

--- --- ---

### Text indexes

Text indexes are IBM Cloudant Query indexes that excel at supporting flexible queries, where the exact fields are not known in advance or use $or and $not operators. Create text indexes to support queries that have these characteristics.

Creating text indexes

When you create a single text index, it's a good practice to use the default values, but some useful index attributes can be modified.

A text index can be partitioned or global; this option is set by using the partitioned field.

Tip: For Full Text Indexes (FTIs), type must be set to text.

The name and ddoc attributes are for grouping indexes into design documents. Use the attributes to refer to index groups by using a custom string value. If no values are supplied for these fields, they're automatically populated with a hash value.

If you create multiple text indexes in a database, with the same ddoc value, you need to know at least the ddoc value and the name value. Creating multiple indexes with the same ddoc value places them into the same design document. Generally, you must put each text index into its own design document.

For more information, see the more about text indexes.

See the following example of a JSON document that requests a partitioned index creation:

{
    "index": {
        "fields": [
            {
                "name": "Movie_name",
                "type": "string"
            }
        ]
    },
    "name": "Movie_name-text",
    "type": "text",
    "partitioned": true
}
See the following example of JSON document that requests a global index creation:

{
    "index": {
        "fields": [
            {
                "name": "Movie_name",
                "type": "string"
            }
        ]
    },
    "name": "Movie_name-text",
    "type": "text",
    "partitioned": false
}
See the following example of a JSON document that requests creation of a more complex partitioned index:

{
    "type": "text",
    "name": "my-index",
    "ddoc": "my-index-design-doc",
    "index": {
        "default_field": {
            "enabled": true,
            "analyzer": "german"
        },
        "selector": {},
        "fields": [
            {"name": "married", "type": "boolean"},
            {"name": "lastname", "type": "string"},
            {"name": "year-of-birth", "type": "number"}
        ]
    },
    "partitioned": true
}

The index field

The index field contains settings specific to text indexes.

To index all fields in all documents automatically, use the simple syntax:

"index": {}
The indexing process traverses all of the fields in all the documents in the database.

In the example movies' demo database, you can see an example of a text index that contains all fields and all documents in a database.

Tip: Take care when you index all fields in all documents for large data sets as it might be a resource-consuming activity.

See the following example of a JSON document that requests creation of an index of all fields in all documents:

{
 "type": "text",
 "index": { }
}
The default_field field

The default_field value specifies how the $text operator can be used with the index.

The default_field includes two keys:

Key
Description
enabled Enable or disable the default_field index. The default value is true.
Table 1. Default_field field keys

The analyzer key in the default_field specifies how the index analyzes text. Later, the index can be queried by using the $text operator. For more information, see the Search documentation for alternative analyzers. You might choose an alternative analyzer when documents are indexed in languages other than English, or when you have other special requirements for the analyzer, such as matching email addresses.

If the default_field isn't specified, or is supplied with an empty object, it defaults to true and the standard analyzer is used.

The fields array

The fields array includes a list of fields that must be indexed for each document. If you know an index queries only on specific fields, then this field can be used to limit the size of the index. Each field must also specify a type to be indexed. The acceptable types are shown in the following list:

"boolean"
"string"
"number"
The index_array_lengths field

IBM Cloudant Query text indexes have a property that is called index_array_lengths. If the property isn't explicitly set, the default value is true.

If the field is set to true, the index requires extra work. This work contains a scan of every document for any arrays, and creating a field to hold the length for each array found.

You might prefer to set the index_array_lengths field to false in the following situations:

You don't need to know the length of an array.
You don't use the $size operator.
The documents in your database are complex, or not completely under your control. As a result, it's difficult to estimate the impact of the extra processing that is needed to determine and store the array lengths.
Tip: The $size operator requires that you set the index_array_lengths field to true. Otherwise, the operator can't work.

See the following example JSON document with suggested settings to optimize performance on production systems:

{
 "default_field": {
  "enabled": false
 },
 "index_array_lengths": false
}
The partitioned field

This field determines whether the created index is a partitioned or global index.

Value
Description
Notes
true Create the index as partitioned. Can be used only in a partitioned database.
false Create the index as global. Can be used in any database.
Table 2. Partitioned field values

The default follows the partitioned setting for the database:

Is the database partitioned?
Default partitioned value
Allowed values
Yes true true, false
No false false
Table 3. Partitioned settings for the database

Advanced: text index internals

The basic premise for full text indexes is that a document is "expanded" into a list of key:value pairs that are indexed by Lucene. This expansion enables the use of Lucene's search syntax as a basis for the query capability.

This technique supports enhanced searches, but does have certain limitations. For example, it might not always be clear whether content for an expanded document came from individual elements or an array.

The query mechanism resolves this uncertainty by preferring to return "false positive" results. In other words, if a match was found because of a search for either an individual element, or an element from an array, then the match is considered a success.

Tip: Like IBM® Cloudant® for IBM Cloud® Search indexes, IBM Cloudant Query indexes of type: text are limited to 200 results when queried.

Selector conversion

A standard Lucene search expression might not fully implement the wanted JSON-based IBM Cloudant query syntax. Therefore, a conversion between the two formats takes place.

In the following example, the JSON query approximates to the English phrase, Match if the age expressed as a number is greater than five and less than or equal to infinity. The Lucene query corresponds to that phrase, where the text _3a within the field name corresponds to the age:number field, and is an example of the document content expansion that was mentioned earlier.

See the following example query to be converted:

{
 "age": {
  "$gt": 5
 }
}
The corresponding Lucene query

(age_3anumber: {5 TO Infinity])
A more complex example

The following example illustrates some important points.

JSON query to be converted to Lucene

{
 "$or": [
  {
   "age": {
    "$gt": 5
   }
  },
  {
   "twitter": {
    "$exists":true
   }
  },
  {
   "type": {
    "$in": [
     "starch",
     "protein"
    ]
   }
  }
 ]
}

The first part of the JSON query is straightforward to convert to Lucene; the test determines whether the age field has a numerical value greater than 5. The { character in the range expression means that the value 5 isn't considered a match.

To implement the "twitter": {"$exists":true} part of the JSON query in Lucene, the first test is to determine whether a twitter field exists. However, the field might be either an array or an object, so the match must succeed when the value is an array or an object.

This requirement means that the $fieldnames field must have entries that contain either twitter.*or twitter:*. The . character is represented in the query as the ASCII character sequence _2e. Similarly, the : character is represented in the query as the ASCII character sequence_3a. This representation requires the use of a two clause OR query for the twitter field, ending in _2e*and_3a*. Implementing this query as two phrases instead of a single twitter* query prevents an accidental match with a field name such as twitter_handle or similar.

The last of the three main clauses are a search for starch or protein. This search is more complicated. The $in operator has some special semantics for array values that are inherited from the way MongoDB behaves. In particular, the $in operator applies to the value or any of the values that are contained in an array that is named by the field. In this example, the expression means that both "type":"starch" and "type":["protein"] would match the example argument to $in. Earlier, the type_3astring expression was converted to type:string. The second type_2e_5b_5d_3astring phrase converts to type.[]:string, which is an example of the expanded array indexing.

Corresponding Lucene query explained

The "#" comments aren't valid Lucene syntax, but help explain the query construction.

(

#### Search for age > 5

 (age_3anumber:[5 TO Infinity])

#### Search for documents that contain the twitter field

 (($fieldnames:twitter_2e*) OR ($fieldnames:twitter_3a*))

#### Search for type = starch

 (
  ((type_3astring:starch) OR (type_2e_5b_5d_3astring:starch))

#### Search for type = protein

  ((type_3astring:protein) OR (type_2e_5b_5d_3astring:protein))
 )
)
--- --- ---

#### Partial indexes

Use partial indexes to create indexes using a subset of the documents of the database. This is a powerful optimisation technique when used correctly: it reduces the overall size of an index, making queries faster and reducing data storage costs.

Creating a partial index

IBM Cloudant Query supports partial indexes by using the partial_filter_selector field. The partial_filter_selector contains a standard IBM Cloudant Query that is executed at index time. Documents that don't match the selector are not added to the index.

See the following example query:

{
  "selector": {
    "status": {
      "$ne": "archived"
    },
    "type": "user"
  }
}
Without a partial index, this query requires a full index scan to find all the documents of type:user that don't have a status of archived. This situation occurs because a normal index can be used to match contiguous rows, and the $ne operator can't guarantee that.

To improve response time, you can create an index that excludes documents with status: { $ne: archived } at index time by using partial_filter_selector shown in the following example:

POST /db/_index HTTP/1.1
Content-Type: application/json
Content-Length: 144
Host: localhost:5984

{
  "index": {
    "partial_filter_selector": {
      "status": {
        "$ne": "archived"
      }
    },
    "fields": ["type"]
  },
  "ddoc" : "type-not-archived",
  "type" : "json"
}

Partial indexes aren't used by the query planner unless specified by a use_index field, so you must modify the original query:

{
  "selector": {
    "status": {
      "$ne": "archived"
    },
    "type": "user"
  },
  "use_index": "type-not-archived"
}
Technically, you don't need to include the filter on the status field in the query selector. The partial index ensures that this value is always true. However, if you include the filter, it makes the intent of the selector clearer. It also makes it easier to take advantage of future improvements to query planning (for example, automatic selection of partial indexes).

--- --- ---
