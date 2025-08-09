
class PDFConverter():
    def convert(
        self,
        output_file_extension: str,
        file_bytes: bytes):
        return 'convertito in pdf'

class TXTConverter():
    def convert(
        self,
        output_file_extension: str,
        file_bytes: bytes):
        return 'convertito in txt'

class FactoryConversion():
    def convert(
        self,
        input_file_extension: str,
        output_file_extension: str,
        file_bytes: bytes):

        if output_file_extension == 'PDF':
            PDFConverter.convert(input_file_extension, file_bytes)

        elif output_file_extension == 'TXT':
            TXTConverter.convert(input_file_extension, file_bytes)

        else:
            pass

