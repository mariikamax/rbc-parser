use strict;
use warnings;
use JSON::PP;
use Encode;

binmode STDOUT, ':encoding(utf8)';
binmode STDERR, ':encoding(utf8)';

print "\n" . "=" x 70 . "\n";
print "  RBC PARSER\n";
print "  chr.rbc.ru -> news | cbr.ru -> currencies\n";
print "=" x 70 . "\n\n";

my $news_url = 'https://chr.rbc.ru/';
my $cbr_url = 'https://www.cbr.ru/scripts/XML_daily.asp';
my $output_file = 'result.json';

my %currencies = ();
my @events = ();

print "Loading news from chr.rbc.ru...\n";

my $html = '';
system("curl -s -L --connect-timeout 10 \"$news_url\" -o \"temp_news.html\" 2>nul");
if (-f 'temp_news.html' && -s 'temp_news.html' > 1000) {
    open(my $fh, '<:encoding(UTF-8)', 'temp_news.html') or die "Cannot open temp_news.html: $!";
    local $/;
    $html = <$fh>;
    close($fh);
    unlink 'temp_news.html';
}

if (!$html || length($html) < 1000) {
    die "ERROR: Cannot load news from chr.rbc.ru\n";
}

print "  Loaded " . length($html) . " bytes\n\n";

print "Parsing news...\n";

my @news = $html =~ /<a[^>]*class="[^"]*news-line-link[^"]*"[^>]*>.*?<span[^>]*class="[^"]*news-line-title[^"]*"[^>]*>(.*?)<\/span>/sg;

if (scalar(@news) == 0) {
    @news = $html =~ /<h[23][^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/sg;
    @news = map { ($1, $2) } @news if scalar(@news) > 0;
}

my $count = 0;
my %seen = ();

for (my $i = 0; $i < scalar(@news); $i++) {
    last if $count >= 10;
    my $title = $news[$i];
    $title =~ s/<[^>]*>//g;
    $title =~ s/^\s+|\s+$//g;
    $title =~ s/\s+/ /g;
    
    next if length($title) < 15;
    next if $seen{$title};
    next if $title =~ /Реклама/i;
    next if $title =~ /^[\d.,\s]+$/;
    
    $seen{$title} = 1;
    push @events, $title;  
    $count++;
}

print "  Found " . scalar(@events) . " news items\n\n";

print "Loading currency rates from CBRF...\n";

my $xml = '';
system("curl -s -L --connect-timeout 10 \"$cbr_url\" -o \"temp_cbr.xml\" 2>nul");
if (-f 'temp_cbr.xml' && -s 'temp_cbr.xml' > 100) {
    open(my $fh, '<:encoding(UTF-8)', 'temp_cbr.xml') or die "Cannot open temp_cbr.xml: $!";
    local $/;
    $xml = <$fh>;
    close($fh);
    unlink 'temp_cbr.xml';
}

if (!$xml || length($xml) < 100) {
    print "  Trying PowerShell...\n";
    system("powershell -Command \"[System.IO.File]::WriteAllText('temp_cbr.xml', (New-Object System.Net.WebClient).DownloadString('$cbr_url'), [System.Text.Encoding]::UTF8)\" 2>nul");
    if (-f 'temp_cbr.xml' && -s 'temp_cbr.xml' > 100) {
        open(my $fh, '<:encoding(UTF-8)', 'temp_cbr.xml') or die "Cannot open temp_cbr.xml: $!";
        local $/;
        $xml = <$fh>;
        close($fh);
        unlink 'temp_cbr.xml';
    }
}

if (!$xml || length($xml) < 100) {
    die "ERROR: Cannot load currency rates from CBRF\n";
}

print "  Loaded " . length($xml) . " bytes\n";

my @needed_codes = ('USD', 'EUR', 'CNY', 'GBP', 'JPY');

foreach my $code (@needed_codes) {
    if ($xml =~ /<Valute.*?<CharCode>$code<\/CharCode>.*?<Value>([\d,]+)<\/Value>/s) {
        my $value = $1;
        $value =~ s/,/./g;
        $currencies{$code} = $value;
    }
}

print "  Found " . scalar(keys %currencies) . " currencies\n\n";

my %result = (
    currencies => \%currencies,
    news => \@events
);

my $json = JSON::PP->new->pretty->canonical->encode(\%result);

open(my $out, '>:encoding(UTF-8)', $output_file) or die "Cannot create $output_file: $!";
print $out $json;
close($out);

print "\n" . "=" x 70 . "\n";
print "DONE! Saved to $output_file\n";
print "=" x 70 . "\n\n";

print "CURRENCIES:\n";
foreach my $code (sort keys %currencies) {
    printf "  %-6s %10s RUB\n", $code, $currencies{$code};
}

print "\nNEWS (first 5):\n";
my $i = 1;
foreach my $title (@events) {
    last if $i > 5;
    print "  $i. $title\n";
    $i++;
}
if (scalar(@events) > 5) {
    print "  ... and " . (scalar(@events) - 5) . " more\n";
}

print "\nFull JSON: $output_file\n";
print "=" x 70 . "\n";