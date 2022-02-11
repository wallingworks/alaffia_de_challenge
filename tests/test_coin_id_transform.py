import unittest
import json

from mock import patch

from app import app

class CoinTransformerTest(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        
    def test_successful_known_coin(self):
        # Given
        payload = json.dumps({
            "coins": ["bitcoin"]
        })

        # When
        response = self.app.post('/coin_id_transform', headers={"Content-Type": "application/json"}, data=payload)

        # Then
        #self.assertEqual(str, type(response.json['id']))
        self.assertEqual(200, response.status_code)
       
    def test_successful_unknown_coin(self):
        # Given
        payload = json.dumps({
            "coins": ["j1b8erishcoin"]
        })

        # When
        response = self.app.post('/coin_id_transform', headers={"Content-Type": "application/json"}, data=payload)
        
        # Then
        #self.assertEqual(str, type(response.json['id']))
        self.assertEqual(200, response.status_code)
        
    def test_successful_blank_coin(self):
        # Given
        payload = json.dumps({
            "coins": ["bitcoin", "", "motacap", ""]
        })
        
        # When
        response = self.app.post('/coin_id_transform', headers={"Content-Type": "application/json"}, data=payload)
        
        # Then
        #self.assertEqual(str, type(response.json['id']))
        self.assertEqual(200, response.status_code)
    
    @patch('app.get_exchanges')
    def test_successful_empty_exchanges(self, mock_get_exchanges):
        
        # Mock
        mock_get_exchanges.return_value = []
        
        # Given
        payload = json.dumps({
            "coins": ["bitcoin",]
        })
        
        # When
        response = self.app.post('/coin_id_transform', headers={"Content-Type": "application/json"}, data=payload)
        
        # Then
        #self.assertEqual(str, type(response.json['id']))
        self.assertEqual(200, response.status_code)
    def tearDown(self):
        pass
    
    """
    Why do these not work??
    """
    def check_csv_200(self, payload):
        # When
        response = self.app.post('/coin_id_transform', headers={"Content-Type": "application/json"}, data=payload)

        # Then
        #self.assertEqual(str, type(response.json['id']))
        self.assertEqual(202, response.status_code)
        
    def check_json_200(self, payload):
        # When
        response = self.app.post('/coin_id_transform', headers={"Content-Type": "text/csv"}, data=payload)

        # Then
        #self.assertEqual(str, type(response.json['id']))
        self.assertEqual(202, response.status_code)
