from turbo_utils.database.create_pipeline_tables import create_pipeline_tables
from datetime import datetime
from astropy.io import votable
from logging import Logger
import psycopg2


class DatabaseError(Exception):
    pass

class DatabaseManager:
    """Mediates the database connection for the Pipeline"""

    def __init__(self, db_details, logger: Logger, schema="pipeline"):
        """Connects to the database and creates the pipeline tables"""
        self.schema = schema
        self.logger = logger

        try:
            self.connection = psycopg2.connect(options=f"-c search_path={schema}",**db_details)
            create_pipeline_tables(self.connection, schema)
            self.connection.close()
            self.connection = psycopg2.connect(options=f"-c search_path={schema}",**db_details)
        except Exception as e:
            output = f"Failed to Connect to Database.\n{type(e).__name__}: {e.args}"
            self.logger.exception(output)
            raise DatabaseError("Failed to Connect to Database.") from e

    def __del__(self):
        """Closes the database connection"""
        if self.connection:
            self.connection.close()

    def exit_cleanup(self):
        """Zeros n_current. Could perform other cleanup"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""UPDATE status SET n_current = 0;""")
                self.connection.commit()

        except Exception as e:
            pass

    def get_image_id(self, image):
        """Returns the sequential id for an image in the database, or -1 if the image is not found in the database"""
        file_path = image.source_path
        with self.connection.cursor() as cursor:
            cursor.execute(f"""SELECT image_id FROM images WHERE file_path = '{file_path}';""")
            value = cursor.fetchone()[0]
            if value is not None:
                return value
            else:
                return -1

    def image_in_database(self, image):
        """Check if an image has an entry in the 'images' table"""
        file_path = image.source_path
        with self.connection.cursor() as cursor:
            cursor.execute(f"""SELECT image_id FROM images WHERE file_path = '{file_path}';""")

            if cursor.fetchone() is not None:
                return True

        return False

    def add_image(self, image):
        """Add an image to the database, creating entries in the 'images' and 'image_status' tables."""
        try:
            try:
                filter = image.hdr["FILTER"]
            except Exception:
                filter = "NONE"

            ra = image.ra if image.ra else "NULL"
            dec = image.dec if image.dec else "NULL"

            # Insert image into images
            with self.connection.cursor() as cursor:
                cursor.execute("""INSERT INTO images(file_path, object_id, ra, dec, filter)
                               VALUES(%s, %s, %s, %s, %s) RETURNING image_id;""",
                               (image.source_path, image.object_id, ra, dec, filter))

                # Set the image's database id
                image_id = cursor.fetchone()[0]
                image.db_id = image_id
                image.hdr.update(DB_ID=image_id)
                image.hdul.close()

                # Insert an entry into the status table
                cursor.execute("""INSERT INTO image_status(image_id, file_path, status, pipeline_step, processing_time)
                               VALUES(%s, %s, 'received', 'received', 0);""",
                               (image_id, image.source_path))

                # Update pipeline status table
                cursor.execute("""UPDATE status SET n_current = n_current + 1
                                   WHERE pipeline_step = 'received';""")

                self.connection.commit()
        except Exception as e:
            self.logger.exception(f"Failed to add the image to the database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to add the image to the database.") from e
        
    def add_new_image(self, image):
        """Check if image is in the database, and add it if it isn't.
        Updates the DB_ID header value if the image is already in the database"""

        if not self.image_in_database(image):
            self.add_image(image)
        else:
            image_id = self.get_image_id(image)
            image.db_id = image_id
            image.hdr.update(DB_ID=image_id)
            image.hdul.close()


    def get_next_image(self):
        """Get the next un-processed image from the 'image_status' table, while setting its status to 'processing'.
        Returns the file path for the image."""
        with self.connection.cursor() as cursor:
            cursor.execute("""UPDATE image_status SET status = 'processing' 
                           WHERE file_path = (
                                SELECT file_path FROM image_status
                                WHERE status = 'received'
                                LIMIT 1
                                FOR UPDATE SKIP LOCKED
                                )
                           RETURNING file_path;""")
            
            try:
                next_image = cursor.fetchone()[0]
            except TypeError:
                next_image = cursor.fetchone()

            return next_image

    def start_image(self, image):
        """Record the image as being processed by the pipeline.
        Checks if an entry has already been created by the telescope."""
        try:
            # Is image in database
            if (image.db_id and
                (image.object_id == self.get_objectId_from_image_table(image.db_id))):
                # Has the image been processed before
                if self.get_step_from_status_table(image.db_id) != "captured":
                    return False
                # Update image table
                with self.connection.cursor() as cursor:
                    cursor.execute("UPDATE images SET file_path = %s, WHERE image_id = %s;",
                                    (image.source_path, image.db_id))
                    self.connection.commit()

                # Update status table
                self.update_image_status(image, "received", 0, "Yes")

                return True

            # Add image to database for first time
            self.add_image(image)
            return True
        except Exception as e:
            self.logger.exception(f"Failed to start the image in the pipeline database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to start the image in the pipeline database.") from e

    def add_exposure(self, filename, object_id, ra, dec, filter):
        """Record that an image has been captured by the camera"""
        try:
            with self.connection.cursor() as cursor:
                # Insert image into images
                cursor.execute("""INSERT INTO images(file_path, object_id, ra, dec, filter)
                                VALUES(%s, %s, %s, %s, %s) RETURNING image_id;""",
                               (filename, object_id, ra, dec, filter))

                # Get the database id of the image
                image_id = cursor.fetchone()[0]

                # Insert an entry into the status table
                cursor.execute("""INSERT INTO image_status(image_id, pipeline_step, processing_time)
                               VALUES(%s, 'captured', 0);""",
                               (image_id,))

                # Update pipeline status table
                cursor.execute("""UPDATE status SET n_current = n_current + 1
                                   WHERE pipeline_step = 'captured';""")

                self.connection.commit()

            return image_id
        except Exception as e:
            self.logger.exception("Failed to add the image to the database.")
            raise DatabaseError("Failed to start the image in the pipeline database.") from e

    def update_image_path(self, image, new_data_path):
        """Not Implemented"""
        return


    def update_image_status(self, image, pipeline_step, step_shortname, runtime, step_message="No"):
        """Updates an image's status in the database including which step it's on and
        its total processing time. Updates the image status and the pipeline status tables."""
        try:
            # Trim completion message
            step_message = step_message[:127]

            old_step = self.get_step_from_status_table(image.db_id)

            # Add the pipeline step to the status table (if it's new)
            self.add_pipeline_step(pipeline_step, step_shortname)

            with self.connection.cursor() as cursor:
                # Set the pipeline step & update processing time in the image status table
                cursor.execute("""UPDATE image_status
                            SET pipeline_step = %s, processing_time = processing_time + %s, step_message = %s
                            WHERE image_id = %s;""",
                            (pipeline_step, runtime, step_message, image.db_id))

                # Update number of images in each step and the total processing time
                # in the pipeline status table
                if pipeline_step != old_step:
                    # Starting step
                    cursor.execute("""UPDATE status SET n_current = n_current + 1
                                   WHERE pipeline_step = %s;""",
                                   (pipeline_step,))
                else:
                    # Finishing step
                    cursor.execute("""UPDATE status SET n_current = n_current - 1,
                                   n_processed = n_processed + 1, total_runtime = total_runtime + %s
                                   WHERE pipeline_step = %s;""",
                                   (runtime, pipeline_step))

                    # Record how long the step took
                    cursor.execute("""INSERT INTO processing_time(image_id, pipeline_step, runtime)
                                   VALUES(%s, %s, %s) ON CONFLICT DO NOTHING;""",
                                   (image.db_id, pipeline_step, runtime))

                self.connection.commit()
        except Exception as e:
            self.logger.exception(f"Failed to update the database image status.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to update the database image status.") from e

    def get_objectId_from_image_table(self, image_id):
        """Query object_id from the image table for an image"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT object_id FROM images WHERE image_id = %s;""",
                               (image_id,))
                value = cursor.fetchone()[0]

                return value
        except Exception as e:
            self.logger.warning(f"Failed to query the database image table.", exc_info=True)
            return None

    def get_step_from_status_table(self, image_id):
        """Query the pipeline_step from the image status table for an image"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT pipeline_step FROM image_status WHERE image_id = %s",
                               (image_id,))
                value = cursor.fetchone()[0]
            return value
        except Exception as e:
            self.logger.warning(f"Failed to query the database image status table.", exc_info=True)
            return None

    def get_step_from_pipeline_status_table(self, pipeline_step):
        """Query a pipeline_step from the pipeline status table"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT pipeline_step FROM status WHERE pipeline_step = %s;""",
                            (pipeline_step,))
                value = cursor.fetchone()
                if value:
                    return value[0]
                return None
        except Exception as e:
            self.logger.warning(f"Failed to query the database pipeline status table.", exc_info=True)
            return None

    def pipeline_step_in_database(self, pipeline_step):
        """Checks if a step is in the database."""
        return self.get_step_from_pipeline_status_table(pipeline_step) is not None

    def add_pipeline_step(self, pipeline_step, shortname):
        """Adds a new pipeline step to the database"""
        if (self.pipeline_step_in_database(pipeline_step)):
            return
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""INSERT INTO status(pipeline_step, shortname, total_runtime, n_processed, n_current)
                               VALUES (%s, %s, 0, 0, 0) ON CONFLICT DO NOTHING;""",
                               (pipeline_step,shortname))
                self.connection.commit()
        except Exception as e:
            self.logger.error(f"Failed to add a pipeline step to the database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to add a pipeline step to the database.") from e

    def assign_reference(self, db_id, reference_path, reference_distance):
        """Updates an image with a reference path and a reference distance."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""UPDATE images
                               SET reference_path = %s, reference_distance = %s
                               WHERE image_id = %s;""",
                               reference_path, reference_distance, db_id)
                self.connection.commit()
        except Exception as e:
            self.logger.exception(f"Failed to assign a reference in the database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to assign a reference in the database.") from e

    def retrieve_closest_image(self, image_id, ra, dec, filter="NONE"):
        """Retrieves the closest image in the database by its RA and DEC coordinate"""
        select_sql = """
        SELECT ra, dec, file_path,
            DEGREES( ACOS(  GREATEST(-1, LEAST(1, SIN( RADIANS(%s)) * SIN( RADIANS(dec)) +
                            COS( RADIANS(%s)) * COS( RADIANS(dec)) * COS(RADIANS(%s - ra)))))
                            )
            AS angular_distance,
            object_id
        FROM images
        WHERE ra IS NOT NULL AND dec IS NOT NULL AND filter = %s
        ORDER BY angular_distance;
        """

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(select_sql, (dec, dec, ra, filter))
                result = cursor.fetchone()
                return result
        except Exception as e:
            self.logger.exception(f"Failed to find a close image pair in the database. {image_id}, {ra}, {dec}\n{type(e).__name__}: {e.args}")
            return None

    def update_ra_dec(self, db_id, ra, dec):
        """Not Implemented"""
        return

    def update_nsources(self, db_id, nsources):
        """Updates the nsources value for an image"""

        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""UPDATE images SET nsources = %s WHERE image_id = %s;""",
                               (nsources, db_id))
                return True
        except Exception as e:
            self.logger.exception(f"Failed to update nsources in the database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to update nsources in the database.") from e
        
    def log_scamp(self, db_id, scamp_xml, dist_path=None, fgroup_path=None, referr1d_path=None, referr2d_path=None):
        """Adds contents of a SCAMP output VOTable file to the database"""
        table = votable.parse(scamp_xml)
        date_proc = table.get_field_by_id_or_name('Date').value + ' ' + table.get_field_by_id_or_name('Time').value

        dist_path = ("'"+str(dist_path)+"'") if dist_path else "NULL"
        fgroup_path = ("'"+str(fgroup_path)+"'") if fgroup_path else "NULL"
        referr1d_path = ("'"+str(referr1d_path)+"'") if referr1d_path else "NULL"
        referr2d_path = ("'"+str(referr2d_path)+"'") if referr2d_path else "NULL"


        stats = table.get_table_by_id('Fields')
        obj_id = stats.array["Image_Ident"][0]
        ra = stats.array["Field_Coordinates"][0][0] / 15
        dec = stats.array["Field_Coordinates"][0][1]
        ref_off = stats.array["AstromOffset_Reference"][0]
        astrom_offset_ref = f'{{{ref_off[0]},{ref_off[1]}}}'
        ref_sigma = stats.array["AstromSigma_Reference"][0]
        astrom_sigma_ref = f'{{{ref_sigma[0]},{ref_sigma[1]}}}'
        ref_corr = stats.array["AstromCorr_Reference"][0]
        ref_chi2 = stats.array["Chi2_Reference"][0]

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"""INSERT INTO scamp_results(image_id, object_id, ra, dec, date_proc, astrom_offset_ref, astrom_sigma_ref, astrom_corr_ref, astrom_chi_ref, dist_map_path, fgroup_map_path, referr_1d_path, referr_2d_path)
                               VALUES({db_id}, '{obj_id}', {ra}, {dec}, '{date_proc}', '{astrom_offset_ref}', '{astrom_sigma_ref}', {ref_corr}, {ref_chi2}, {dist_path}, {fgroup_path}, {referr1d_path}, {referr2d_path});""")
                return True
        except Exception as e:
            self.logger.exception(f"Failed to add scamp results to the database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to add scamp results to the database.") from e

    def image_found(self, object_id):
        """Checks if an image has been seen before based on its object_id"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT file_path, object_id FROM images WHERE object_id = %s;""",
                                (object_id,))
                result = cursor.fetchone()
                return (result is not None)
        except Exception as e:
            self.logger.error(f"Failed to find the requested image in the database.\n{type(e).__name__}: {e.args}")
            return False

    def flat_found(self, object_id):
        """Checks if a flat has been seen before based on its object_id"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT file_path, object_id FROM flats WHERE object_id = %s;""",
                                (object_id,))
                result = cursor.fetchone()
                return (result is not None)
        except Exception as e:
            self.logger.error(f"Failed to find the requested image in the database.\n{type(e).__name__}: {e.args}")
            return False

    def bias_found(self, object_id):
        """Checks if a bias has been seen before based on its object_id"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT file_path, object_id FROM biases WHERE object_id = %s;""",
                                (object_id,))
                result = cursor.fetchone()
                return (result is not None)
        except Exception as e:
            self.logger.error(f"Failed to find the requested image in the database.\n{type(e).__name__}: {e.args}")
            return False

    def dark_found(self, object_id):
        """Checks if a dark has been seen before based on its object_id"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT file_path, object_id FROM darks WHERE object_id = %s;""",
                                (object_id,))
                result = cursor.fetchone()
                return (result is not None)
        except Exception as e:
            self.logger.error(f"Failed to find the requested image in the database.\n{type(e).__name__}: {e.args}")
            return False

    def add_flat(self, path, telescope, filter, date, type):
        """Adds the flat to the flats table"""
        try:
            with self.connection.cursor() as cursor:
                object_id = f"flat_{telescope}_{filter}_{date}_{type}"
                cursor.execute("""INSERT INTO flats(file_path, object_id, telescope, filter, type, date_obs, downloaded)
                               VALUES(%s, %s, %s, %s, %s, %s, %s);""",
                               (path, object_id, telescope, filter, type, date, "false"))

                self.connection.commit()
        except Exception as e:
            self.logger.exception(f"Failed to add the flat to the database.", exc_info=True)
            raise DatabaseError("Failed to add the flat to the database.") from e

    def download_flat(self, path, telescope, filter, date, type):
        """Mark the flat as downloaded. Updates the path if the flat exists in the
        database already. Otherwise, inserts a new entry."""
        try:
            with self.connection.cursor() as cursor:
                object_id = f"flat_{telescope}_{filter}_{date}_{type}"
                cursor.execute("""SELECT COUNT(1)
                                FROM flats
                                WHERE object_id = %s;""",
                                (object_id,))
                if cursor.fetchone() == 1:
                    cursor.update("""UPDATE flats
                                  SET path=%s, downloaded=true
                                  WHERE object_id = %s""",
                                  (path, object_id))
                else:
                    cursor.execute("""INSERT INTO flats(file_path, object_id, telescope, filter, type, date_obs, downloaded)
                                VALUES(%s, %s, %s, %s, %s, %s, %s);""",
                                (path, object_id, telescope, filter, type, date, "true"))

                self.connection.commit()
        except Exception as e:
            self.logger.exception(f"Failed to mark the flat as downloaded in the database.", exc_info=True)
            raise DatabaseError("Failed to mark the flat as downloaded in the database.") from e

    def get_flat(self, telescopeName, filter, date: datetime):
        """Returns the filepath and timestamp of closest flat by time.
            Only looks at flats from the same telescope and filter
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT file_path, date_obs
                                FROM flats
                                WHERE downloaded=TRUE AND telescope=%s AND filter=%s
                                ORDER BY ABS(EXTRACT(EPOCH FROM AGE(date_obs, %s::TIMESTAMPTZ))) asc
                                LIMIT 1;""",
                                (telescopeName, filter, date.strftime("%Y-%m-%d %H:%M:%S %Z")))
                if cursor.rowcount == 0:
                    return None, None
                filepath, timestamp = cursor.fetchone()
                return filepath, timestamp
        except Exception as e:
            self.logger.exception(f"Failed to find flat in database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to find flat in database.") from e

    def add_bias(self, bias):
        """Adds the hdul information from bias to the biases table"""
        if self.bias_found(bias.object_id):
            return False
        try:
            bias_datetime =  datetime.strptime(bias.date_obs, '%Y-%m-%d %H:%M:%S.%f')
            with self.connection.cursor() as cursor:
                cursor.execute("""INSERT INTO biases(file_path, object_id, camera, date_obs)
                               VALUES(%s, %s, %s, %s) RETURNING image_id;""",
                               (bias.source_path, bias.object_id, bias.hdr["CAMERA"], bias_datetime))
                # Get the image id
                bias_id = cursor.fetchone()[0]
                bias.db_id = bias_id

                self.connection.commit()
            return True
        except Exception as e:
            self.logger.exception(f"Failed to add the bias to the database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to add the bias to the database.") from e

    def get_bias(self, camera_id):
        """Returns the filepath of the most time recent bias .fits file
        based on the unique camera id"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT file_path FROM biases
                               WHERE camera=%s ORDER BY date_obs desc;""",
                               (camera_id,))
                bias_filepath = cursor.fetchone()[0]
                self.connection.commit()
            return bias_filepath
        except Exception as e:
            self.logger.exception(f"Failed to find bias in database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to find bias in database.") from e

    def add_dark(self, dark):
        """Adds the hdul information from dark to the darks table"""
        if self.bias_found(dark.object_id):
            return False
        try:
            dark_datetime =  datetime.strptime(dark.date_obs, '%Y-%m-%d %H:%M:%S.%f')
            with self.connection.cursor() as cursor:
                cursor.execute("""INSERT INTO darks(file_path, object_id, camera, date_obs)
                               VALUES(%s, %s, %s, %s) RETURNING image_id;""",
                               (dark.source_path, dark.object_id, dark.hdr["CAMERA"], dark_datetime))

                # Get the database id of the image
                dark_id = cursor.fetchone()[0]
                dark.db_id = dark_id

                self.connection.commit()
            return True
        except Exception as e:
            self.logger.exception(f"Failed to add the dark to the database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to add the dark to the database.") from e

    def get_dark(self, camera_id):
        """Returns the filepath of the most time recent dark .fits file based on the unique camera id"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""SELECT file_path FROM darks WHERE camera=%s
                               ORDER BY date_obs desc;""",
                               (camera_id,))
                dark_filepath = cursor.fetchone()[0]

                self.connection.commit()
            return dark_filepath
        except Exception as e:
            self.logger.exception(f"Failed to find dark in database.\n{type(e).__name__}: {e.args}")
            raise DatabaseError("Failed to find dark in database.") from e

    def _delete_databse(self):
        """Removes the current Pipeline schema - PERMANENTLY

        THIS IS NOT REVERSIBLE!"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"DROP SCHEMA {self.schema} CASCADE;")
                self.connection.commit()
        except Exception as e:
            self.logger.error(f"Failed to delete the database schema.\n{type(e).__name__}: {e.args}")
            return False

