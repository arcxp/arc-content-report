# Boston Globe - Removing Low Value Wires Images

# EXTERNAL

Boston Globe
January 23, 2024

# Contacts

Billy Kirchen: Billy.Kirchen@washpost.com

# Background

The Boston Globe has been an Arc XP client since 2018. In that time, they have been ingesting wires from various sources and adding both the wires story and image content into Arc XP. Many of these images were imported into Photo Center but not assigned to the story as either part of the ANS properties for `content_elements` (the body of the article) or `promo_items.basic` (the featured media of the article). Sometimes these images were used only in the ANS property `related_content` where they have no use at all in the rendered story. 

When a wire story comes in and is published, all the images associated with it are published, including the images that automatically get added to `related_content`. These images aren't live on the site, but they are costing storage space and money. For old wire content, the client is less concerned at the prospect of losing an image that was once used in a wire article body; however, featured media art is critical to maintain in case the story is ever used in a content source because the featured media is what appears as part of the story lead.

The Boston Globe wants to reduce the storage costs that not-used or less important images in Photo Center are costing them. To that end, Boston Globe has determined these criteria:

If the image is

- published
- from a wire
- not in the lead art

then delete it.

The Boston Globe would like to find published wire images that are not featured media (`promo_items.basic`) and remove them from Photo Center on Arc XP.

# Recommendation Summary
1. Using the Photo Center UI filters and examining the resulting browser URL or using the Global Settings Distributor UI, locate the `id` value of a wires photo distributor.
2. Search the Photo Center API to locate wire images and retain the `arc ids` of images returned from the search.
3. Query Elasticsearch for articles that use the image `arc ids` from the retained list.
4. When search results are found, examine the story ANS to see in which fields the image `arc ids` are used.
5. Delete images from the Photo Center API that do not appear in any article’s ANS `promo_items.basic` property. 
## Locate the ID value of a wires photo distributor

Filter the Photo Center UI and copy a specific query parameter that will be exposed in the URL of the Photo Center UI. When using the Photo Center UI, you can filter by one of the wires checkboxes in the margin, then read the updated URL when the filter is applied and pick out the query param `&source={value}` . You can then use this parameter and its value in a query filter in Photo API to use in your own query.

![&source=226329 is the parameter and value for filtering photos by the Associated Press wires source](https://paper-attachments.dropboxusercontent.com/s_720A315A37A84D42E6E98064EA61DC31A5FBD7E543800CD6015507C02231F3A9_1706204327646_image.png)


The Global Settings Distributors page has distributors that you can also use to filter for photos in Photo API. From the Settings tile on your Admin home page, scroll to the Distributors, select a distributor, and examine the URL. The last segment of the URL is the distributor ID. If the selected distributor is configured to deliver images, you can use this ID value in your Photo API query and copy a specific path segment of a specific distributor URL.

![&distributorId=51f4665d-39d2-4d82-8212-3d53cd93a43a is the parameter and value for querying for AFP wires images](https://paper-attachments.dropboxusercontent.com/s_720A315A37A84D42E6E98064EA61DC31A5FBD7E543800CD6015507C02231F3A9_1706204910809_image.png)

## Find limited subset of wires photos to evaluate

When you conduct a search of Photo API, decide on the scope of the filters you want to apply. Because you want to return a limited subset that you can process fully, consider iterating on this search until you process through and locate the desired number of photos to delete from Photo Center.

If your search filter includes dates, you must convert a date into a unix timestamp in milliseconds.


- Pick one day (from 01/01/2020 12:00 AM to 01/02/2020 12:00 AM)
- Limit by Date Uploaded
- Limit by photos that are assigned the wires source type
- Limit by Published state

An example of a Photo API query params that limit in this way is: `startDateUploaded=1577854800000&endDateUploaded=1577941140000&published=true&sourceType=wires&sort=-created_date&limit=100` 

This search, which filters by date (01/01/2020) but not by a specifically named wire source, returns 1615 records. Adding an additional filter for a specific wire `&source=226329` (Associated Press) returns 1450 records. Changing the filter again to remove the date restriction entirely and adding a different specific wire filter `&distributorId=51f4665d-39d2-4d82-8212-3d53cd93a43a` (AFP) returns seven records.

![Boston Globe Photos filtered by Associated Press (226329) on 01/01/2020](https://paper-attachments.dropboxusercontent.com/s_720A315A37A84D42E6E98064EA61DC31A5FBD7E543800CD6015507C02231F3A9_1706203589479_Xnip2024-01-25_12-25-40.jpg)


In Photo API, a query that returns the same results as the previous Photo Center filter looks like:


    curl --request GET \
      --url 'https://api.bostonglobe.arcpublishing.com/photo/api/v2/photos?startDateUploaded=1577854800000&endDateUploaded=1577941140000&source=226329&sourceType=wires&published=true' \
      --header 'Authorization: Bearer <token>'

A JSON filter tool can process the results of this query to show only the Arc IDs of the images that are returned. The following examples uses JSONPath to filter the response and return a list of IDs.


    $.[*]._id
    [
      "IE6DZ5BM4MI6VD4VAILYJDPHLI",
      "RSCCVJRM44I6VDRNAEL665BH5U",
      "UVAU3TRNCEI6VD4VAILYJDPHLI",
      ...
    ]

This query returns 1450 images, uploaded on a single day, and belonging to a single wires source. The point of the restriction in the query is to ensure that the number of images in the batch can be processed in an acceptable amount of time, and are small enough to be verified after the process is complete. The filter parameters can be modified to increase the number of results as appropriate. For instance, if the date filter is changed to one month and other filters are the same (from 01/01/2020 12:00 am to 01/31/2020 12:59 PM and published Associated Press wire photos), the query returns 80226 records. You can find the number of items returned by the query in the headers that are returned by the query response.

![](https://paper-attachments.dropboxusercontent.com/s_720A315A37A84D42E6E98064EA61DC31A5FBD7E543800CD6015507C02231F3A9_1706207155495_image.png)


To paginate through result sets that are greater than one set of 100 results (`&limit=100`), add the offset query parameter and increase it as needed each time you run the query until you process all items. For example, adding `&offset=802258` to the previous query returns a result set containing only the last record.

## Search Content API for stories, filtering by previously queried image IDs

The next step is to query for any story that uses these photo IDs and determine if the ID is used as featured media. Content API can accept a full-text query parameter and look for the requested value in any [indexed, searchable](https://docs.arcxp.com/alc?sys_kb_id=928567d3c37e31501fe095ff05013101&id=kb_article_view&sysparm_rank=1&sysparm_tsqueryId=fec55b8447c04610a87626c2846d4338) ANS field. 

You can find the image ID if it is used in

- a `content_elements` item
- a featured image that is in `promo_items.basic`

You won’t be able to find stories that use that image in

- a featured image that is any other `promo_items` child, such as `promo_items.lead_art`
- images stored in `related_content`
- images that are part of a custom oembed object

Having taken a brief glimpse at Boston Globe’s story content, we don’t see evidence that there is use of `promo_items.lead_art` in this organization, so the limitation of not being able to find image id uses in that field seems acceptable. Similarly, the requirements as understood do not include preserving any uses in `related_content`. It would best serve the requirements if one could search specifically for image ids used in `related_content`, so we could specifically determine if these images should be deleted, but `related_content` is not an indexed ANS field.

Looping over every image ID, run a full text Content API query, similar to this:


    https://api.bostonglobe.arcpublishing.com/content/v4/search
    ?website=bostonglobe
    &published=true
    &_sourceInclude=promo_items.basic.url,content_elements.url,related_content
    &q=IE6DZ5BM4MI6VD4VAILYJDPHLI #full text query using an image arc id

Review the results of the full-text Content API search and manually or programmatically examine the fields where image IDs are used, then build a modified list of image IDs that are not used as a featured media item.

![Shows the searched-for image id IE6DZ5BM4MI6VD4VAILYJDPHLI in the content_elements. This image id can remain in the list of ids to be deleted.](https://paper-attachments.dropboxusercontent.com/s_720A315A37A84D42E6E98064EA61DC31A5FBD7E543800CD6015507C02231F3A9_1706214242871_image.png)

![Shows that the story has a featured media element that uses a DIFFERENT image than the one that was searched for, IE6DZ5BM4MI6VD4VAILYJDPHLI. If the searched-for image id had showed in this field, then it would be removed from the list of ids to be delted.](https://paper-attachments.dropboxusercontent.com/s_720A315A37A84D42E6E98064EA61DC31A5FBD7E543800CD6015507C02231F3A9_1706214291427_image.png)


If an image is used as featured media, it should not be part of the list of image IDs that can be deleted. The new list of image IDs, containing IDs that are either not used in a story at all, or are used in any field other than `promo_items.basic` will then be used to delete from the Photo API.

## Delete images from Photo API

After you generate a modified list of image IDs, loop over this new list and process a `DELETE` Photo API call to remove the images. 

After you delete an image in Arc XP, a wire story that used it shows a “denormalization error” message in Composer at the location where it had been placed. This message is viewable only in Composer. No error appears if a user views the story online, on mobile, or rendered in any front-end application other than in Composer.


![An example of denormalization errors in the Composer interface.  The item on the left is in the body of the story.  The item on the right is in the related contents.](https://paper-attachments.dropboxusercontent.com/s_720A315A37A84D42E6E98064EA61DC31A5FBD7E543800CD6015507C02231F3A9_1706543464538_image.png)


To avoid the Composer “denormalization error” message, you can programmatically rewrite the wire story using Draft API to remove the ANS element containing the image reference. Because denormalization errors are not breaking errors in the delivery or experience of a wire story, this step is not mandatory given the requirements of the project.

# Questions

Is Boston Globe willing to accept the risk that deleted wires images may have been used in a wires story’s `content_elements` property, also known as the article’s body?

Is Boston Globe willing to accept the risk that deleted wires images may have been used in a wires story’s `promo_items.lead_art`  or other non-`promo_items.basic` child of the `promo_items` property, which some clients use as a different source of the featured media image, and cannot be searched from or filtered for?  

# APPENDIX

[**Arc XP Photo API Documentation**](https://docs.arcxp.com/alc?sys_kb_id=9358c451c3b279101fe095ff05013139&id=kb_article_view&sysparm_rank=1&sysparm_tsqueryId=196b7a5147884a10a87626c2846d438c)

[**Content API: Query Reference**](https://docs.arcxp.com/alc?sys_kb_id=928567d3c37e31501fe095ff05013101&id=kb_article_view&sysparm_rank=1&sysparm_tsqueryId=11bbb29147884a10a87626c2846d436b) - Lists the indexed fields that can be used to filter Content API queries.

# 

