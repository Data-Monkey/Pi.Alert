<?php

// ###################################
// ## Languages
// ###################################

$defaultLang = "en_us";
$allLanguages = ["en_us","es_es","de_de"];

global $db;

$result = $db->querySingle("SELECT Value FROM Settings WHERE Code_Name = 'UI_LANG'"); 
switch($result){
  case 'Spanish': $pia_lang_selected = 'es_es'; break;
  case 'German': $pia_lang_selected = 'de_de'; break;
  default: $pia_lang_selected = 'en_us'; break;
}

if (isset($pia_lang_selected) == FALSE or (strlen($pia_lang_selected) == 0)) {$pia_lang_selected = $defaultLang;}

require dirname(__FILE__).'/../skinUI.php';

$result = $db->query("SELECT * FROM Plugins_Language_Strings");
$strings = array();
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $strings[$row['String_Key']] = $row['String_Value'];
}


// Load data from JSON files 
function getLanguageDataFromJson()
{
    global $allLanguages;

    // Array to hold the language data from the JSON files
    $languageData = [];
    
    // Load and parse the JSON data from .json files
    foreach ($allLanguages as $language) {
      $data = json_decode(file_get_contents(dirname(__FILE__).'/'.$language.'.json'), true); 
      $languageData[$language] = $data[$language];
    }

    return $languageData;
}


// Merge the JSON data with the SQL data, giving priority to SQL data for overlapping keys
function mergeLanguageData($jsonLanguageData, $sqlLanguageData)
{
    // Loop through the JSON language data and check for overlapping keys
    foreach ($jsonLanguageData as $languageCode => $languageStrings) {
        foreach ($languageStrings as $key => $value) {
            // Check if the key exists in the SQL data, if yes, use the SQL value
            if (isset($sqlLanguageData[$key])) {
                $jsonLanguageData[$languageCode][$key] = $sqlLanguageData[$key];
            }
        }
    }

    return $jsonLanguageData;
}

function lang($key)
{
  global $pia_lang_selected, $lang, $defaultLang, $strings, $db;
  // Get the data from JSON files
  $languageData = getLanguageDataFromJson();

  // Get the data from SQL query  
  $sqlLanguageData = $strings;

  // Merge JSON data with SQL data
  $mergedLanguageData = mergeLanguageData($languageData, $sqlLanguageData);

  $result = $mergedLanguageData[$pia_lang_selected][$key] ?? "String Not found for key ".$key;

  return $result;
};


