# Cloudant Query Cheatsheet

| Condition Operator | Argument             | Purpose                                                                                |
| ------------------ | -------------------- | -------------------------------------------------------------------------------------- |
| $eq, $ne           | Any JSON value       | Equal, Not equal                                                                       |
| $lt, $lte          | Any JSON value       | Lesser, Lesser or equal,                                                               |
| $gt, $gte          | Any JSON value       | Greater, Greater or equal                                                              |
| $exists            | Boolean              | Check field exists or not                                                              |
| $type              | String               | Check field type, accepts: "null", "boolean", "number", "string", "array" and "object" |
| $in, $nin          | Array of JSON values | Field must exist / not exist                                                           |
| $size              | Integer              | Match length of an array field                                                         |
| $mod               | [Divisor, Remainder] | Matches   field % Divisor == Remainder                                                 |
| $regex             | String               | String value matches a regex                                                           |

| Combination Operators | Argument | Purpose                                                                                        |
| --------------------- | -------- | ---------------------------------------------------------------------------------------------- |
| $and                  | Array    | Matches if ALL the selectors in the array match                                                |
| $or                   | Array    | Matches if ANY of the selectors in the array match                                             |
| $nor                  | Array    | Matches if NONE of the selectors in the array match                                            |
| $not                  | Selector | Matches if the given selector does not match                                                   |
| $all                  | Array    | Matches an array value if it contains all the elements of the argument array                   |
| $elemMatch            | Selector | Matches an array field with AT LEAST ONE element that matches ALL the specified query criteria |
| $allMatch             | Selector | Matches an array field with ALL elements matching ALL the specified query criteria             |
| $keyMapMatch          | Selector | Matches a map that contains AT LEAST ONE key that matches ALL the specified query criteria     |

## Example

```json
{
  "selector": {
    "_id": {
      "$gt": "0"
    }
  },
  "fields": [
    "_id",
    "_rev"
  ],
  "sort": [
    {
      "_id": "asc"
    }
  ]
}
```
