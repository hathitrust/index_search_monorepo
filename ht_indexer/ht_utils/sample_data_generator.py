"""
        if remote_file:
            # Download document .zip and .mets.xml file
            # TODO: Check if file exist
            download_document_file(
                source_path=self.source_path, target_path=self.target_path, extension="zip"
            )

            # Download document .zip and .mets.xml file
            # TODO: Check if file exist
            download_document_file(
                source_path=self.source_path,
                target_path=self.target_path,
                extension="mets.xml",
            )

@staticmethod
    def clean_up_folder(document_path, list_ids):
        logger.info("Cleaning up .xml and .Zip files")

        for id_name in list_ids:
            # zip file
            list_documents = glob.glob(f"{document_path}/{id_name}.zip")
            for file in list_documents:
                logger.info(f"Deleting file {file}")
                os.remove(file)
            list_documents = glob.glob(f"{document_path}/{id_name}.mets.xml")
            for file in list_documents:
                logger.info(f"Deleting file {file}")
                os.remove(file)


        """
