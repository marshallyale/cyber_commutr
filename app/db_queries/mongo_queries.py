def weekly_aggregator(strava_id):
    pipeline = [
        {"$match": {"athlete.id": strava_id}},
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
                    "week": {"$week": "$date_field"},
                    "month": {"$month": "$date_field"},
                    "year": {"$year": "$date_field"},
                },
                "total": {"$sum": "$distance"},
            }
        },
        {"$sort": {"_id.year": -1, "_id.month": -1, "_id.week": -1}},
    ]
    return pipeline
