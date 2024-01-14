def weekly_aggregator(strava_id, last_date):
    pipeline = [
        {"$match": {"athlete.id": strava_id}}, 
        {"$match": {"$dateFromString": {
                    "dateString": "$start_date"
                }, {
            "$gt": {last_date
                
            }
        }
    }},
        {
            "$project": {
                "_id": 1,
                "date_field": {
                    "$dateFromString": {
                        "dateString": "$start_date"  # Assuming 'date_field' is the timestamp string field
                    }
                },
                "distance": "$distance",  # Include other fields as needed
            }
        },
        {
            "$group": {
                "_id": {
                    "week": {"$isoWeek": "$date_field"},
                    "year": {"$isoWeekYear": "$date_field"},
                },
                "total": {"$sum": "$distance"},
            }
        },
        {"$sort": {"_id.year": -1, "_id.week": -1}},
        {
            "$project": {
                "_id": 0,
                "total": 1,
                "year_week": {
                    "$concat": [
                        {"$toString": "$_id.year"},
                        "-",
                        {"$toString": "$_id.week"},
                    ]
                },
            }
        },
    ]
    return pipeline
