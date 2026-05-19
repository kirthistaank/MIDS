# Airbnb listing feature helpers (sourced from databnb_final.Rmd)

#' Return 1 if the amenity pattern appears in the listing amenities string, else 0.
has_amenity <- function(amenity, column) {
  as.integer(stringr::str_detect(column, amenity))
}

#' Build modeling frame for one calendar year (from last_review), matching the report pipeline.
#' @param airbnb_data Raw listings as read from the Inside Airbnb extract.
#' @param year Integer year (e.g. 2024L).
prepare_listings_for_year <- function(airbnb_data, year) {
  stopifnot(is.data.frame(airbnb_data), length(year) == 1L)

  listings <- airbnb_data %>%
    dplyr::filter(!is.na(.data$last_review)) %>%
    dplyr::mutate(
      date = as.Date(.data$last_review),
      year = lubridate::year(.data$date)
    ) %>%
    dplyr::filter(.data$year == !!year)

  cols <- c(
    "neighbourhood_cleansed", "latitude", "longitude", "property_type",
    "room_type", "accommodates", "bedrooms", "amenities", "minimum_nights",
    "beds", "price", "availability_60", "availability_365", "number_of_reviews",
    "year", "number_of_reviews_l30d", "number_of_reviews_ly",
    "estimated_revenue_l365d", "availability_30", "availability_90",
    "estimated_occupancy_l365d", "neighbourhood_group_cleansed",
    "review_scores_rating"
  )

  df_filtered <- listings %>% dplyr::select(dplyr::all_of(cols))

  df_filtered <- df_filtered %>%
    dplyr::mutate(
      price = readr::parse_number(gsub("\\$", "", .data$price)),
      num_amenities = dplyr::if_else(
        is.na(.data$amenities) | .data$amenities == "{}",
        0L,
        as.integer(stringr::str_count(.data$amenities, ",") + 1L)
      )
    ) %>%
    dplyr::filter(!is.na(.data$price))

  df_filtered %>%
    dplyr::mutate(
      is_entire_home = as.integer(.data$property_type == "Entire home/apt"),
      is_private_room = as.integer(.data$room_type == "Private room"),
      is_shared_room = as.integer(.data$room_type == "Shared room"),
      has_wifi = has_amenity("Wifi", .data$amenities),
      has_kitchen = has_amenity("Kitchen", .data$amenities),
      has_pool = has_amenity("Pool", .data$amenities),
      has_parking = has_amenity("Free parking|Paid parking", .data$amenities),
      has_hot_tub = has_amenity("Hot tub|Jacuzzi", .data$amenities),
      has_ac = has_amenity("Air conditioning", .data$amenities)
    )
}
